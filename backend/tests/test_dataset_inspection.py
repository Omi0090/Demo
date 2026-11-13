"""Synthetic fixtures test software behavior only; never used as project data."""
import pandas as pd
import pytest

from ml.preprocessing.inspect_dataset import FILES, inspect_dataset


@pytest.fixture
def dataset(tmp_path):
    tables = {
        "providers": {"Provider": ["P1", "P2"], "PotentialFraud": ["Yes", "No"]},
        "beneficiaries": {"BeneID": ["B1", "B2"]},
        "inpatient": {"Provider": ["P1", "P1"], "BeneID": ["B1", "B1"], "ClaimID": ["C1", "C1"], "Amount": [100, 100]},
        "outpatient": {"Provider": ["P2"], "BeneID": ["B2"], "ClaimID": ["C2"], "Amount": [None]},
    }
    for role, table in tables.items():
        pd.DataFrame(table).to_csv(tmp_path / FILES[role], index=False)
    return tmp_path


def test_profile_across_chunks(dataset):
    report = inspect_dataset(dataset, chunksize=1)
    assert report["files"]["inpatient"]["duplicate_records"] == 1
    assert report["files"]["inpatient"]["columns"]["Provider"]["inferred_role"] == "identifier"
    assert report["files"]["outpatient"]["columns"]["Amount"]["missing"] == 1
    assert report["files"]["providers"]["label_distribution"] == {"Yes": 1, "No": 1}
    assert report["relationships"]["inpatient"]["distinct_patients_without_beneficiary_record"] == 0


def test_missing_files(tmp_path):
    with pytest.raises(FileNotFoundError, match="Missing dataset files"):
        inspect_dataset(tmp_path)


def test_invalid_schema(dataset):
    pd.DataFrame({"wrong": [1]}).to_csv(dataset / FILES["providers"], index=False)
    with pytest.raises(ValueError, match="observed"):
        inspect_dataset(dataset)


def test_orphans_and_unexpected_labels(dataset):
    pd.DataFrame({"Provider": ["unknown"], "BeneID": ["unknown"], "ClaimID": ["C2"]}).to_csv(dataset / FILES["outpatient"], index=False)
    pd.DataFrame({"Provider": ["P1"], "PotentialFraud": ["invalid"]}).to_csv(dataset / FILES["providers"], index=False)
    result = inspect_dataset(dataset)
    assert result["relationships"]["outpatient"]["distinct_providers_without_label_record"] == 1
    assert result["warnings"]


def test_invalid_chunk_size(dataset):
    with pytest.raises(ValueError, match="positive"):
        inspect_dataset(dataset, 0)


def test_chunk_size_does_not_change_report(dataset):
    assert inspect_dataset(dataset, 1) == inspect_dataset(dataset, 100)


def test_partial_requires_opt_in(dataset):
    (dataset / FILES["outpatient"]).unlink()
    with pytest.raises(FileNotFoundError):
        inspect_dataset(dataset)
    report = inspect_dataset(dataset, allow_partial=True)
    assert report["complete"] is False
    assert report["missing_files"] == [FILES["outpatient"]]
    assert report["relationships"]["claim_ids_shared_across_types"] is None
    assert "inpatient" in report["files"]


def test_partial_without_reference_tables(dataset):
    (dataset / FILES["providers"]).unlink()
    (dataset / FILES["beneficiaries"]).unlink()
    report = inspect_dataset(dataset, allow_partial=True)
    assert report["relationships"]["inpatient"]["distinct_providers_without_label_record"] is None


def test_partial_empty_folder(tmp_path):
    with pytest.raises(FileNotFoundError, match="No dataset files"):
        inspect_dataset(tmp_path, allow_partial=True)
