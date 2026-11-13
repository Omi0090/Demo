# Initial EDA — actual complete dataset

Executed `python -m ml.preprocessing.prepare` successfully on all four uploaded files.

- 558,211 claims: 40,474 inpatient and 517,737 outpatient.
- All 5,410 labeled providers and 138,556 beneficiaries have observed claims.
- No unparseable nonmissing claim dates or amount strings in the checked fields.
- No negative reimbursement/deductible amounts or negative claim durations.
- No negative inpatient hospitalization durations.
- Reimbursement median: 80; mean: approximately 997.01; 90th percentile: 2,000; 95th: 5,000; 99th: 17,000; maximum: 125,000 (source monetary units).
- Strong right skew means raw amount alone cannot establish suspicious activity; differentiate claim types and compare to training-only baselines.
- 5,719 claims have no computable earlier-date provider mean. Preserve unknown-history state rather than inventing a baseline.
- Existing missing source values remain missing for later training-only imputation. No claim fraud target is introduced.

Local outputs: compressed prepared claims, compressed provider features, and `eda.json` containing quality diagnostics, descriptive reimbursement statistics, class/type counts and monthly claim/reimbursement totals.

This is initial EDA, not a completed clinical/data-quality audit or predictive evaluation. Date-of-birth/death semantics, clinical combinations, fold fitting, temporal generalization, training and SHAP remain pending. A clean parse does not imply medically valid or legitimate billing.
