"""Read-only, chunked profiling of the four Medicare source CSV files.

Identifiers are kept as strings. No labels or model features are inferred here.
Only aggregate diagnostics (never individual patient records) are written out.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import pandas as pd

FILES = {
    "providers": "Train-1542865627584.csv",
    "beneficiaries": "Train_Beneficiarydata-1542865627584.csv",
    "inpatient": "Train_Inpatientdata-1542865627584.csv",
    "outpatient": "Train_Outpatientdata-1542865627584.csv",
}
# These are relationship contracts to validate, not assumed feature schemas.
REQUIRED = {
    "providers": {"Provider", "PotentialFraud"},
    "beneficiaries": {"BeneID"},
    "inpatient": {"Provider", "BeneID", "ClaimID"},
    "outpatient": {"Provider", "BeneID", "ClaimID"},
}


def inspect_dataset(data_dir: Path, chunksize: int = 25000, allow_partial: bool = False) -> dict:
    if chunksize < 1:
        raise ValueError("chunksize must be positive")
    missing_files = [name for name in FILES.values() if not (data_dir / name).is_file()]
    if missing_files and not allow_partial:
        raise FileNotFoundError("Missing dataset files: " + ", ".join(missing_files))
    if len(missing_files) == len(FILES):
        raise FileNotFoundError("No dataset files found")
    report = {
        "files": {}, "relationships": {}, "warnings": [],
        "complete": not missing_files, "missing_files": missing_files,
    }
    if missing_files:
        report["warnings"].append("PARTIAL DATASET: inspection only; not ready for final training.")
    keys = {}
    for role, filename in FILES.items():
        path = data_dir / filename
        if not path.is_file():
            continue
        header = pd.read_csv(path, nrows=0).columns.tolist()
        absent = REQUIRED[role] - set(header)
        if absent:
            raise ValueError(f"{filename}: missing linkage/target columns {sorted(absent)}; observed {header}")
        rows = 0
        missing = Counter()
        numeric = Counter()
        nonmissing = Counter()
        labels = Counter()
        seen_rows = set()
        duplicates = 0
        identifiers = {k: set() for k in ("Provider", "BeneID", "ClaimID") if k in header}
        id_counts = Counter()
        for chunk in pd.read_csv(path, dtype="string", chunksize=chunksize):
            rows += len(chunk)
            missing.update(chunk.isna().sum().to_dict())
            for column in header:
                values = chunk[column].dropna()
                nonmissing[column] += len(values)
                numeric[column] += int(pd.to_numeric(values, errors="coerce").notna().sum())
            # Fixed-size digests keep duplicate detection bounded per unique row.
            for record in chunk.itertuples(index=False, name=None):
                canonical = json.dumps([None if pd.isna(v) else v for v in record], ensure_ascii=False)
                digest = hashlib.sha256(canonical.encode()).digest()
                if digest in seen_rows:
                    duplicates += 1
                seen_rows.add(digest)
            for key in identifiers:
                values = chunk[key].dropna()
                identifiers[key].update(values.tolist())
                id_counts[key] += len(values)
            if role == "providers":
                labels.update(chunk["PotentialFraud"].fillna("<missing>").tolist())
        columns = {}
        for column in header:
            is_identifier = column in {"Provider", "BeneID", "ClaimID"} or column.endswith("Physician")
            kind = "identifier" if is_identifier else (
                "numeric_candidate" if nonmissing[column] and numeric[column] == nonmissing[column]
                else "categorical_or_date_candidate"
            )
            if column == "PotentialFraud":
                kind = "target"
            columns[column] = {
                "read_dtype": "string", "inferred_role": kind,
                "missing": int(missing[column]),
                "missing_percent": round(100 * missing[column] / rows, 3) if rows else None,
            }
        result = {
            "filename": filename, "rows": rows, "columns": columns,
            "duplicate_records": duplicates,
            "repeated_identifiers": {k: id_counts[k] - len(v) for k, v in identifiers.items()},
        }
        if role == "providers":
            result["label_distribution"] = dict(labels)
            result["label_percentages"] = {k: round(100*v/rows, 3) for k,v in labels.items()} if rows else {}
            unexpected = set(labels) - {"Yes", "No"}
            if unexpected:
                report["warnings"].append(f"Unexpected provider labels: {sorted(unexpected)}")
            if len(labels) < 2:
                report["warnings"].append("Provider target has fewer than two observed classes.")
        if not rows:
            report["warnings"].append(f"{filename} contains no records.")
        report["files"][role] = result
        keys[role] = identifiers
    for role in ("inpatient", "outpatient"):
        if role not in keys:
            continue
        report["relationships"][role] = {
            "distinct_providers_without_label_record": (
                len(keys[role]["Provider"] - keys["providers"]["Provider"]) if "providers" in keys else None
            ),
            "distinct_patients_without_beneficiary_record": (
                len(keys[role]["BeneID"] - keys["beneficiaries"]["BeneID"]) if "beneficiaries" in keys else None
            ),
        }
    report["relationships"]["claim_ids_shared_across_types"] = (
        len(keys["inpatient"]["ClaimID"] & keys["outpatient"]["ClaimID"])
        if "inpatient" in keys and "outpatient" in keys else None
    )
    report["leakage_review"] = [
        "Exclude PotentialFraud and all derived labels from predictors.",
        "Never use arbitrary identifiers as numeric predictors.",
        "Split provider IDs before fitting imputers, encoders, scaling, thresholds or resampling.",
        "Provider-local aggregates may use that provider's available claims; population baselines must be fitted on training providers only.",
        "For prospective claim scoring, calculate historical features using strictly earlier dates, excluding the current claim.",
        "This retrospective dataset does not establish future performance or verified claim fraud.",
    ]
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("ml/data"))
    parser.add_argument("--output", type=Path, default=Path("reports/dataset_inspection.json"))
    parser.add_argument("--chunksize", type=int, default=25000)
    parser.add_argument("--allow-partial", action="store_true", help="Inspect available files; mark report incomplete")
    args = parser.parse_args()
    report = inspect_dataset(args.data_dir, args.chunksize, allow_partial=args.allow_partial)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Inspection saved to {args.output}")


if __name__ == "__main__":
    main()
