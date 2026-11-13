# Implemented feature dictionary

All IDs and clinical codes remain strings. Dates parse with explicit YYYY-MM-DD format. Invalid values become missing with diagnostics; raw sources remain unchanged. Numerical imputation/scaling and population thresholds are deliberately deferred to fold-fitted ML pipelines.

## Claim features
- `claim_duration_days`: ClaimEndDt minus ClaimStartDt, elapsed days (same-day = 0); negative durations become missing.
- `invalid_duration`: missing date or negative claim duration.
- `hospitalization_days`: DischargeDt minus AdmissionDt for inpatient only; negative duration becomes missing; outpatient unknown/not applicable.
- `diagnosis_count`, `procedure_count`: nonmissing numbered diagnosis/procedure slots. Admitting diagnosis is not counted again.
- `deductible_missing`: missing or unparseable deductible indicator.
- `claim_type`: source inpatient/outpatient, not a fraud label.
- `patient_historical_claim_count`, `provider_historical_claim_count`: all claims for that key whose ClaimStartDt is strictly earlier. Same-day claims excluded. Missing dates give unknown history.
- `provider_historical_average`: earlier-date reimbursement sum divided by earlier-date nonmissing reimbursement count. No history gives missing, not zero.
- `claim_to_provider_average_ratio`: current amount divided by historical average. Missing/zero denominator gives missing.

These historical features assume that earlier-starting claims are available at scoring time. The dataset lacks adjudication/arrival timestamps, so operational availability is unverified. They are chronological retrospective features, not demonstrated production-time guarantees.

## Retrospective provider features
Computed independently for each provider using its observed source claims; never target-derived:
- `total_claims`: record count.
- `total_reimbursement`: reimbursement sum (all missing stays missing).
- `average_claim_amount`, `maximum_claim_amount`, `minimum_claim_amount`: reimbursement mean/max/min.
- `unique_patients`: distinct BeneIDs.
- `unique_physicians`: distinct IDs across all three physician roles; missing excluded.
- `inpatient_claim_count`, `outpatient_claim_count`: source-type counts.
- `average_hospitalization_days`: mean known inpatient stay duration.
- `average_deductible`: mean nonmissing deductible.
- `diagnosis_diversity`, `procedure_diversity`: distinct codes across numbered slots, excluding missing.
- `duplicate_candidate_count`: number of records belonging to a repeated billing signature (provider, patient, dates, type, amount, and all numbered diagnosis/procedure slots). Requires known dates/amount. All members counted, not only excess rows. Physician and deductible differences are not part of this definition. This is a retrospective review indicator, not proven duplicate billing.
- `duplicate_candidate_ratio`: candidate count / total claims.
- `average_claims_per_patient`: total claims / distinct patients.
- `maximum_to_average_ratio`: maximum reimbursement / provider mean; zero mean gives missing.
- `has_observed_claims`: coverage indicator. Providers without records retain missing aggregates, not invented activity.

`PotentialFraud` is retained only as the supervised target in the provider artifact; exclude it and `Provider` from predictors. Claim artifacts do not contain the provider label.

## Memory and artifacts
The inspector is chunked, but this initial preparation implementation loads both claim sources and materializes history joins in RAM. It succeeded on the supplied 558,211 records in the development sandbox; limited-RAM Windows performance is not verified. Avoid claiming constant-memory processing. SQLite/PostgreSQL staging or partitioned processing is needed if laptop memory is insufficient.

Outputs in ignored `reports/prepared/` contain sensitive record-level data; do not publish them. Gzip CSV consumers must explicitly read IDs/codes as strings. Outputs are not yet the final versioned model artifact contract.

## Additional implemented features and rules

- `local_high_cost_ratio`: fraction of a provider's claims exceeding twice its own retrospective mean amount. This is **provider-local**, not a population-fitted threshold or fraud indicator.
- `monthly_reimbursement_std`: population standard deviation of provider monthly totals across its own first-to-last observed month, filling internal absent months with zero.
- `monthly_reimbursement_slope`: least-squares slope of those totals versus month index (amount per month).
- `normalized_monthly_slope`: slope divided by provider mean monthly reimbursement; zero mean gives 0. Uses only that provider's observed span, not another provider's calendar boundaries.
- Claim fit-reference 99th-percentile amount, median/MAD and primary diagnosis/first-procedure pair counts: fitted only from the training-provider sample.
- Explicit rules: amount > reference 99th percentile; >5x prior provider mean; >50 prior patient claims; repeated full signature; repeated primary procedure for patient/provider/date; pair frequency <=1 in training; robust amount deviation >50.

Claim numerical matrix: amount, deductible, duration, diagnosis count, procedure count, patient prior count, provider prior mean, amount/prior-mean ratio, inpatient indicator. Fold-fitted provider median imputation and scaling and claim fit-reference median/scaling are implemented. No arbitrary ID or provider target appears in that matrix.

Duplicate/repeated-procedure rules are **retrospective** review logic, not current-only predictive features. They include same-day repetitions and must not be described as strictly prospective. Rule indicators are stored separately from numerical anomaly scores. Beneficiary clinical features and population high-cost provider ratio are not used; the source has insufficient timing metadata to safely use annual beneficiary totals as prospective features.
