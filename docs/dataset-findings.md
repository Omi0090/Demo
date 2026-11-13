# Actual dataset inspection — partial upload

Three uploaded CSVs were copied into ignored `ml/data/` and inspected with:

```powershell
python -m ml.preprocessing.inspect_dataset --allow-partial
```

Full column-by-column results are generated locally in `reports/dataset_inspection.json`. This document contains aggregate findings only, not patient records.

## Coverage and integrity

| Source | Rows | Exact duplicate rows | Repeated primary IDs |
|---|---:|---:|---:|
| Provider labels | 5,410 | 0 | 0 |
| Beneficiaries | 138,556 | 0 | 0 |
| Inpatient claims | 40,474 | 0 | 0 |
| Outpatient claims | Not supplied | Unknown | Unknown |

Inpatient claims cover 2,092 distinct providers and 31,289 distinct patients. All inpatient provider IDs link to provider labels, and all inpatient BeneIDs link to beneficiaries. Cross-type ClaimID uniqueness cannot yet be checked. Repeated Provider/BeneID values in claims are expected one-to-many relationships, not duplicate primary records.

Provider labels: `No` = 4,904 (90.647%); `Yes` = 506 (9.353%). The minority class requires stratification and training-only class imbalance treatment. These are provider labels, not claim labels.

## Observed schema and semantic decisions

Provider table contains only `Provider` and `PotentialFraud`: no hospital names or verified hospital attributes.

Beneficiaries contain BeneID, DOB/DOD, demographics, coverage months, chronic-condition codes and annual inpatient/outpatient reimbursement/deductible totals. Numeric-looking demographic and condition codes are categorical until their coding is verified. `DOD` is missing for 137,135 records; absence must not be treated as a random numeric missing value or proof of a known death status.

Inpatient columns include claim/provider/patient identifiers; claim/admission/discharge dates; reimbursement/deductible amounts; three physician fields; admitting diagnosis and diagnosis group; ten diagnosis slots; six procedure slots. Preserve all clinical codes as strings, including numeric-looking codes and leading zeros. All fields are intentionally read as strings during inspection; the JSON reports lexical numeric candidates, not finalized training dtypes.

Notable inpatient missingness:
- AttendingPhysician: 112
- OperatingPhysician: 16,644
- OtherPhysician: 35,784
- DeductibleAmtPaid: 899
- ClmDiagnosisCode_10: 36,547
- ClmProcedureCode_1: 17,326
- ClmProcedureCode_6: 40,474 (entire column)

Missing diagnosis/procedure slots generally require presence/count indicators, not invented codes. The entirely empty procedure slot must not become a spurious predictor. Deductible imputation must fit only on training folds and retain a missingness indicator. Dates require explicit parsing and invalid/negative-duration checks during preprocessing; this initial profiler does not validate date chronology.

## Leakage review

- Do not merge PotentialFraud into claim features or encode IDs as numbers.
- Beneficiary annual reimbursement and deductible totals may include the current or future claim. Exclude them from prospective claim predictors unless observation timing is established.
- Provider historical means, patient counts, duplicate patterns, and rare-code baselines must exclude the current/future claim for prospective scoring. Same-day claim ordering is unknown; use strictly earlier dates.
- Split providers before fitting population thresholds, preprocessing, tuning or class balancing. Retrospective provider-local aggregates are not prospective validation.
- With outpatient absent, providers without inpatient claims must not be represented as genuinely inactive. Final provider aggregates and models are deferred.

## Next gate

Supply `Train_Outpatientdata-1542865627584.csv`, then rerun the inspector **without** `--allow-partial`, validate cross-source IDs and date/amount semantics, and proceed to EDA/preprocessing. No ML model has been trained from this partial upload.

## Full upload received — supersedes partial coverage status above

Retrieved the linked Drive file `Train_Outpatientdata-1542865627584.csv` (77,391,090 bytes) and moved it into ignored `ml/data/`. Reran inspection without `--allow-partial`: `complete = true`.

- Outpatient rows: **517,737**; total inpatient + outpatient claims: **558,211**.
- Outpatient exact duplicate rows: **0**; repeated outpatient ClaimIDs: **0**.
- Outpatient coverage: **5,012** distinct providers, **133,980** distinct beneficiaries.
- Both claim sources have **0** provider or beneficiary references absent from their reference tables.
- ClaimIDs shared between inpatient and outpatient: **0**.
- Outpatient header has 27 observed columns. Unlike inpatient, it has no AdmissionDt, DischargeDt or DiagnosisGroupCode; these cannot be assumed for all claim types.
- Provider class distribution remains 506 Yes / 4,904 No.

The generated JSON now covers all four actual files. This completes initial structural profiling, not preprocessing: date chronology, amount semantics, clinical-code handling, business-key duplicate rules and feature engineering remain to implement. No model has yet been trained.
