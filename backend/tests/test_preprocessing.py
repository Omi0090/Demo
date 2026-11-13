"""Synthetic unit-test inputs only, never training data."""
import pandas as pd
import pytest
from ml.preprocessing.prepare import clean_claims, add_history, provider_features


def raw():
    return pd.DataFrame({
        "ClaimID": ["C1", "C2", "C3"], "Provider": ["P1"]*3, "BeneID": ["B1"]*3,
        "ClaimStartDt": ["2009-01-01", "2009-01-01", "2009-01-02"],
        "ClaimEndDt": ["2009-01-01", "2009-01-01", "2009-01-03"],
        "InscClaimAmtReimbursed": ["100", "200", "900"], "DeductibleAmtPaid": ["0", None, "5"],
        "ClmDiagnosisCode_1": ["001", "001", "002"], "ClmProcedureCode_1": [None]*3,
        "AttendingPhysician": ["D1"]*3,
    }, dtype="string")


def test_history_excludes_current_and_same_day():
    cleaned, _ = clean_claims(raw(), "outpatient")
    history = add_history(cleaned).set_index("ClaimID")
    assert history.loc["C1", "patient_historical_claim_count"] == 0
    assert pd.isna(history.loc["C2", "provider_historical_average"])
    assert history.loc["C3", "provider_historical_average"] == 150
    assert history.loc["C3", "claim_to_provider_average_ratio"] == 6
    assert history.loc["C3", "patient_historical_claim_count"] == 2


def test_invalid_values_flagged_not_silently_fixed():
    data = raw()
    data.loc[0, "ClaimEndDt"] = "2008-01-01"
    data.loc[1, "ClaimStartDt"] = "not-a-date"
    data.loc[2, "InscClaimAmtReimbursed"] = "inf"
    cleaned, quality = clean_claims(data, "inpatient")
    assert quality["invalid_duration_rows"] == 2
    assert quality["invalid_amounts"]["InscClaimAmtReimbursed"] == 1
    assert cleaned.loc[0, "ClmDiagnosisCode_1"] == "001"
    assert pd.isna(cleaned.loc[0, "claim_duration_days"])
    assert pd.isna(add_history(cleaned).loc[1, "patient_historical_claim_count"])


def test_provider_features():
    cleaned, _ = clean_claims(raw(), "outpatient")
    labels = pd.DataFrame({"Provider": ["P1", "P2"], "PotentialFraud": ["Yes", "No"]})
    features = provider_features(cleaned, labels).set_index("Provider")
    assert features.loc["P1", "total_claims"] == 3
    assert features.loc["P1", "total_reimbursement"] == 1200
    assert features.loc["P1", "diagnosis_diversity"] == 2
    assert features.loc["P1", "unique_physicians"] == 1
    assert features.loc["P2", "has_observed_claims"] == 0


def test_duplicate_candidate_not_claim_label():
    data = raw()
    data.loc[1, "InscClaimAmtReimbursed"] = "100"
    cleaned, _ = clean_claims(data, "outpatient")
    labels = pd.DataFrame({"Provider": ["P1"], "PotentialFraud": ["Yes"]})
    features = provider_features(cleaned, labels)
    assert features.loc[0, "duplicate_candidate_count"] == 2
    assert "PotentialFraud" not in cleaned


def test_missing_schema_and_duplicate_ids():
    with pytest.raises(ValueError, match="Missing columns"):
        clean_claims(pd.DataFrame(), "inpatient")
    data = raw()
    data.loc[1, "ClaimID"] = "C1"
    with pytest.raises(ValueError, match="Duplicate ClaimID"):
        clean_claims(data, "outpatient")
