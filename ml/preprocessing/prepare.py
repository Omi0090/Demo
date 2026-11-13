"""Validated retrospective provider features and earlier-date claim history.

No population-based thresholds are fitted here: those belong inside training folds.
Generated record-level files are local artifacts, not source-controlled datasets.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ml.preprocessing.inspect_dataset import FILES

DATES = ["ClaimStartDt", "ClaimEndDt", "AdmissionDt", "DischargeDt"]
AMOUNTS = ["InscClaimAmtReimbursed", "DeductibleAmtPaid"]
PHYSICIANS = ["AttendingPhysician", "OperatingPhysician", "OtherPhysician"]


def clean_claims(raw: pd.DataFrame, claim_type: str) -> tuple[pd.DataFrame, dict]:
    if claim_type not in {"inpatient", "outpatient"}:
        raise ValueError("Unknown claim type")
    required = {"ClaimID", "BeneID", "Provider", "ClaimStartDt", "ClaimEndDt", *AMOUNTS}
    absent = required - set(raw.columns)
    if absent:
        raise ValueError(f"Missing columns: {sorted(absent)}")
    frame = raw.copy()
    if frame[["ClaimID", "BeneID", "Provider"]].isna().any().any():
        raise ValueError("Missing linkage identifiers")
    if frame["ClaimID"].duplicated().any():
        raise ValueError("Duplicate ClaimID")
    quality = {"rows": len(frame), "invalid_dates": {}, "invalid_amounts": {}, "negative_amounts": {}}
    for col in DATES:
        if col in frame:
            original = frame[col]
            parsed = pd.to_datetime(original, format="%Y-%m-%d", errors="coerce")
            quality["invalid_dates"][col] = int((original.notna() & parsed.isna()).sum())
            frame[col] = parsed
    for col in AMOUNTS:
        original = frame[col]
        parsed = pd.to_numeric(original, errors="coerce").astype(float)
        invalid = original.notna() & (~np.isfinite(parsed))
        quality["invalid_amounts"][col] = int(invalid.sum())
        frame[col] = parsed.mask(~np.isfinite(parsed))
        quality["negative_amounts"][col] = int((frame[col] < 0).sum())
    frame["claim_type"] = claim_type
    duration = (frame.ClaimEndDt - frame.ClaimStartDt).dt.days
    frame["invalid_duration"] = duration.lt(0) | duration.isna()
    frame["claim_duration_days"] = duration.mask(duration.lt(0))
    quality["invalid_duration_rows"] = int(frame.invalid_duration.sum())
    if claim_type == "inpatient" and {"AdmissionDt", "DischargeDt"} <= set(frame):
        stay = (frame.DischargeDt - frame.AdmissionDt).dt.days
        frame["hospitalization_days"] = stay.mask(stay.lt(0))
        quality["negative_hospitalization_rows"] = int(stay.lt(0).sum())
    else:
        frame["hospitalization_days"] = np.nan
    diag = [c for c in frame if c.startswith("ClmDiagnosisCode_")]
    proc = [c for c in frame if c.startswith("ClmProcedureCode_")]
    frame["diagnosis_count"] = frame[diag].notna().sum(axis=1)
    frame["procedure_count"] = frame[proc].notna().sum(axis=1)
    frame["deductible_missing"] = frame.DeductibleAmtPaid.isna()
    return frame, quality


def add_history(claims: pd.DataFrame) -> pd.DataFrame:
    """Same-day claims cannot see each other; missing dates get unknown history."""
    out = claims.copy()
    for key, prefix in [("BeneID", "patient"), ("Provider", "provider")]:
        valid = out.dropna(subset=["ClaimStartDt"])
        daily = valid.groupby([key, "ClaimStartDt"], observed=True).agg(
            count=("ClaimID", "size"), amount=("InscClaimAmtReimbursed", "sum"),
            amount_count=("InscClaimAmtReimbursed", "count"),
        ).sort_index().reset_index()
        for name in ["count", "amount", "amount_count"]:
            daily[f"prior_{name}"] = daily.groupby(key, sort=False)[name].cumsum() - daily[name]
        daily[f"{prefix}_historical_claim_count"] = daily.prior_count
        keep = [key, "ClaimStartDt", f"{prefix}_historical_claim_count"]
        if key == "Provider":
            daily["provider_historical_average"] = daily.prior_amount / daily.prior_amount_count.replace(0, np.nan)
            keep.append("provider_historical_average")
        out = out.merge(daily[keep], on=[key, "ClaimStartDt"], how="left", validate="many_to_one", sort=False)
    out["claim_to_provider_average_ratio"] = out.InscClaimAmtReimbursed / out.provider_historical_average.replace(0, np.nan)
    return out


def provider_features(claims: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    if labels.Provider.duplicated().any() or labels.Provider.isna().any():
        raise ValueError("Provider label IDs must be unique and present")
    if not labels.PotentialFraud.isin(["Yes", "No"]).all():
        raise ValueError("Unexpected provider target")
    work = claims.copy()
    work["inpatient"] = work.claim_type.eq("inpatient").astype(int)
    work["outpatient"] = work.claim_type.eq("outpatient").astype(int)
    # A review indicator, NOT proof of duplicate billing or verified fraud.
    signature = ["Provider", "BeneID", "ClaimStartDt", "ClaimEndDt", "claim_type", "InscClaimAmtReimbursed"]
    signature += [c for c in work if c.startswith(("ClmDiagnosisCode_", "ClmProcedureCode_"))]
    eligible = work[["ClaimStartDt", "ClaimEndDt", "InscClaimAmtReimbursed"]].notna().all(axis=1)
    work["duplicate_candidate"] = eligible & work.duplicated(signature, keep=False)
    result = work.groupby("Provider", observed=True).agg(
        total_claims=("ClaimID", "size"), total_reimbursement=("InscClaimAmtReimbursed", lambda x: x.sum(min_count=1)),
        average_claim_amount=("InscClaimAmtReimbursed", "mean"), maximum_claim_amount=("InscClaimAmtReimbursed", "max"),
        minimum_claim_amount=("InscClaimAmtReimbursed", "min"), unique_patients=("BeneID", "nunique"),
        inpatient_claim_count=("inpatient", "sum"), outpatient_claim_count=("outpatient", "sum"),
        average_hospitalization_days=("hospitalization_days", "mean"),
        average_deductible=("DeductibleAmtPaid", "mean"), duplicate_candidate_count=("duplicate_candidate", "sum"),
    )
    for columns, name in [([c for c in PHYSICIANS if c in work], "unique_physicians"),
                          ([c for c in work if c.startswith("ClmDiagnosisCode_")], "diagnosis_diversity"),
                          ([c for c in work if c.startswith("ClmProcedureCode_")], "procedure_diversity")]:
        # Concatenate one slot at a time, avoiding a dense all-column melt.
        pairs = pd.concat([work[["Provider", col]].rename(columns={col: "value"}).dropna() for col in columns], ignore_index=True) if columns else pd.DataFrame(columns=["Provider", "value"])
        result[name] = pairs.groupby("Provider").value.nunique().reindex(result.index, fill_value=0)
    result["average_claims_per_patient"] = result.total_claims / result.unique_patients
    result["duplicate_candidate_ratio"] = result.duplicate_candidate_count / result.total_claims
    # Provider-local, retrospective dispersion; no held-out population threshold.
    result["maximum_to_average_ratio"] = result.maximum_claim_amount / result.average_claim_amount.replace(0, np.nan)
    means = work.groupby("Provider").InscClaimAmtReimbursed.transform("mean")
    result["local_high_cost_ratio"] = (work.InscClaimAmtReimbursed.gt(2 * means)).groupby(work.Provider).mean()
    monthly = work.assign(month=work.ClaimStartDt.dt.to_period("M")).dropna(subset=["month"])
    monthly = monthly.groupby(["Provider", "month"]).InscClaimAmtReimbursed.sum()
    trend_rows = {}
    if len(monthly):
        for pid, values in monthly.groupby(level=0):
            local = values.droplevel(0)
            months = pd.period_range(local.index.min(), local.index.max(), freq="M")
            x = np.arange(len(months), dtype=float)
            amounts = local.reindex(months, fill_value=0).to_numpy(dtype=float)
            mean = amounts.mean()
            slope = float(np.polyfit(x, amounts, 1)[0]) if len(x)>1 else 0.0
            trend_rows[pid] = {"monthly_reimbursement_std": float(amounts.std()), "monthly_reimbursement_slope": slope, "normalized_monthly_slope": slope / mean if mean else 0.0}
        result = result.join(pd.DataFrame.from_dict(trend_rows, orient="index"))
    output = labels.merge(result.reset_index(), on="Provider", how="left", validate="one_to_one")
    output["has_observed_claims"] = output.total_claims.notna().astype(int)
    return output


def prepare(data_dir: Path, output: Path) -> dict:
    missing = [f for f in FILES.values() if not (data_dir / f).is_file()]
    if missing:
        raise FileNotFoundError(f"All four source files required: {missing}")
    labels = pd.read_csv(data_dir / FILES["providers"], dtype="string")
    beneficiary_ids = pd.read_csv(data_dir / FILES["beneficiaries"], usecols=["BeneID"], dtype="string")
    tables, quality = [], {}
    for kind in ["inpatient", "outpatient"]:
        table, quality[kind] = clean_claims(pd.read_csv(data_dir / FILES[kind], dtype="string"), kind)
        tables.append(table)
    claims = pd.concat(tables, ignore_index=True)
    if claims.ClaimID.duplicated().any():
        raise ValueError("ClaimID collision across sources")
    if not claims.Provider.isin(labels.Provider).all() or not claims.BeneID.isin(beneficiary_ids.BeneID).all():
        raise ValueError("Claims contain orphan linkage IDs")
    quality["status"] = "review_required" if any(
        sum(q["invalid_dates"].values()) + sum(q["invalid_amounts"].values()) + q["invalid_duration_rows"]
        for q in quality.values()
    ) else "validated_structural_and_value_checks"
    features = provider_features(claims, labels)
    claims = add_history(claims)
    eda = {
        "quality": quality, "claims": len(claims), "providers": len(labels),
        "observed_providers": int(claims.Provider.nunique()), "observed_patients": int(claims.BeneID.nunique()),
        "reimbursement": claims.InscClaimAmtReimbursed.describe(percentiles=[.5, .9, .95, .99]).to_dict(),
        "claim_type_counts": claims.claim_type.value_counts().to_dict(),
        "provider_target_counts": labels.PotentialFraud.value_counts().to_dict(),
        "monthly": claims.assign(month=claims.ClaimStartDt.dt.strftime("%Y-%m")).groupby("month").agg(
            claims=("ClaimID", "size"), reimbursement=("InscClaimAmtReimbursed", "sum")
        ).reset_index().to_dict(orient="records"),
        "history_unknown_rows": int(claims.provider_historical_average.isna().sum()),
    }
    output.mkdir(parents=True, exist_ok=True)
    # Compressed local artifacts retain codes/IDs; consumers must load codes as strings.
    features.to_csv(output / "provider_features.csv.gz", index=False, compression="gzip")
    claims.to_csv(output / "claims_prepared.csv.gz", index=False, compression="gzip")
    (output / "eda.json").write_text(json.dumps(eda, indent=2, allow_nan=False), encoding="utf-8")
    return eda


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("ml/data"))
    parser.add_argument("--output", type=Path, default=Path("reports/prepared"))
    args = parser.parse_args()
    result = prepare(args.data_dir, args.output)
    print(json.dumps({k: result[k] for k in ["quality", "claims", "providers", "observed_providers"]}, indent=2))
