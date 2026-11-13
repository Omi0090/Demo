# Final-year report and viva preparation

## Suggested report structure

1. **Title page / certificate / declaration / acknowledgments.** Use the complete project title; identify institution, students and supervisor.
2. **Abstract.** Describe provider classification, unverified claim anomalies, separate hybrid outputs, real Medicare source, explainability and local application. Report actual selected-model metrics from `model-comparison.md`, not invented claims of 99% fraud accuracy.
3. **Introduction.** Insurance review challenges, costly false positives/negatives, role of decision support, scope and objectives.
4. **Literature review.** Compare supervised fraud prediction, Isolation Forest, local density methods, rule systems and SHAP. Cite papers actually read; distinguish literature findings from this project's results.
5. **Problem formulation.** Provider-level target PotentialFraud; unlabeled claim-level unusualness; explicit definitions of risk, anomaly and confirmed fraud.
6. **Requirements / feasibility.** Local Windows hardware/software, privacy constraints, user roles, functional/nonfunctional requirements and latency/resource considerations.
7. **Dataset understanding / EDA.** Four actual tables, observed column inventory, source provenance/limitations, primary relationships, class imbalance, missingness, date/amount validation and source hashes.
8. **System design.** Architecture diagram from architecture document; ER diagram with 11 tables; login/prediction/export sequence diagrams; API contracts; UI navigation and trust boundaries.
9. **Preprocessing and features.** Explain codes as strings, preserved linkage, provider-local aggregation, strict earlier-date history, missingness, fold-fitted median/scaling and leakage safeguards. State in-memory limitations.
10. **Provider modeling.** 80/20 provider stratification, three-fold training CV, search grids, weighting, fixed threshold, average precision selection, final fit and serialization. Include actual comparison and confusion matrix.
11. **Claim anomaly methods.** Fit-reference sampling, IF/LOF assumptions, score units, contamination, robust median/MAD, duplicate/repetition and rare-pair indicators. Explain why no supervised claim fraud metrics exist.
12. **Explainability / hybrid engine.** Actual selected-model SHAP, training background for linear model, base values and output units, additivity test, separate provider/claim signals and human interpretation.
13. **Implementation.** PostgreSQL schema/migrations/transactions/indexes, JWT/Argon2/roles, REST API, React charts/search/pagination/themes, CSV/PDF exports and audit logs.
14. **Testing.** Unit test matrix; actual database/API tests; browser workflow; negative permissions/invalid inputs; commands/results and known warnings. Do not describe Windows tests as executed when only instructions exist.
15. **Results and discussion.** Report model precision/recall tradeoffs, review burden, internal validation limits, retrospective feature availability and potential bias.
16. **Conclusion / future work.** Independent future-time validation, calibration, reviewer feedback, clinical vocabularies, streaming processing and stronger privacy controls.
17. **References / appendices.** Original dataset URL/license terms, official library docs, actual papers read, feature dictionary, API summary, setup guide and screenshots from your run. Do not attach identifiable beneficiary records.

## Ten-minute demonstration

- 0–1 min: problem and correct distinction between provider labels and claim anomalies.
- 1–2 min: real data counts/relationships and integrity checks.
- 2–4 min: provider search, held-out tag, model probability and signed SHAP.
- 4–6 min: claim filters, separate IF/LOF scores, explicit indicators, associated provider risk and live re-inference.
- 6–7 min: alert review, administrator/analyst distinction.
- 7–8 min: provider/physician analytics and charts computed from DB.
- 8–9 min: model comparison, confusion matrix and precision/recall tradeoff.
- 9–10 min: CSV/PDF download, test report and honest limitations/future work.

## Viva questions and concise answers

**1. Why two ML modules?** The provider table has observed labels; claims do not. Supervised classification is appropriate for one and unsupervised/rule-based review for the other.

**2. Can you mark every claim from a Yes provider as fraudulent?** No. That would fabricate a claim target, introduce label leakage and make an unsupported accusation.

**3. What is the join structure?** Provider joins labels to claims, BeneID links beneficiaries, and validated unique ClaimID links diagnoses/procedures and anomaly outputs.

**4. Why exclude IDs from numeric predictors?** They are arbitrary linkage identifiers. Treating their values as magnitudes encourages memorization without clinical/billing meaning.

**5. What is class imbalance here?** 506 of 5,410 providers are labeled Yes (about 9.35%). Accuracy alone can hide poor minority recall.

**6. How is imbalance handled?** Balanced class weights for sklearn classifiers and training-label negative/positive ratio for XGBoost, without synthetic claim fraud labels or test resampling.

**7. Why split providers, not individual claims, for provider classification?** Provider is the supervised unit. Claims from a provider must not leak across that unit's training and holdout membership.

**8. How are preprocessing leaks prevented?** Median imputation and scaling are inside the CV pipeline and fit only on training folds. Provider-local aggregates do not borrow other providers' claims. Population anomaly references fit on training providers.

**9. What does PR-AUC mean here?** Non-interpolated average precision from sklearn; explicitly state that convention rather than confusing it with trapezoidal PR integration.

**10. How is the winning model selected?** Highest training three-fold CV average precision. A different model can perform better on a particular holdout metric without being selected.

**11. Is predict_proba calibrated?** Not necessarily. The UI explicitly labels provider probabilities uncalibrated. Calibration and external validation are future work.

**12. What does Isolation Forest detect?** Points isolated by shorter random partition paths. We negate score_samples so larger displayed values mean more unusual observations.

**13. Why novelty=True for LOF?** It permits scoring new observations with a fitted reference set. Fit-set novelty scores are descriptive and not equivalent to evaluation on new claims.

**14. What does the 5% contamination mean?** A reference threshold assumption used by anomaly models; it is not an estimate of true fraud prevalence.

**15. How do you avoid current-claim contamination in history?** Aggregate by entity/date, subtract that day's aggregate from the cumulative sum, and exclude all same-day claims. Missing dates yield unknown history.

**16. Why can historical features still be operationally imperfect?** The dataset has start dates but no arrival/adjudication timestamps, so availability of earlier-starting claims at real scoring time is unverified.

**17. How do duplicate rules work?** Repeated provider/patient/date/type/amount/clinical-code signatures are retrospective review indicators. Legitimate repetitions remain possible; no accusation is made.

**18. Is a rare diagnosis/procedure pair invalid?** Not necessarily. Rarity in the training reference is an explainable review signal, not a clinical compatibility judgment.

**19. What does SHAP explain?** Additive contributions to the actual selected fitted model's output relative to a baseline, in explicitly stated units. It explains model behavior, not causation.

**20. How do you verify SHAP?** Sum baseline plus contributions, apply sigmoid for log-odds output, and compare against predict_proba; maximum error must be <=1e-4.

**21. Why not combine claim and provider scores into one probability?** They refer to different units/tasks and lack a calibrated common target. Combining them would imply unsupported probability semantics.

**22. Why PostgreSQL and normalization?** Foreign keys, transactions and indexes maintain linkage; diagnosis/procedure child tables avoid repeated multi-value claim attributes. Sparse original attributes/features use JSON deliberately.

**23. How are passwords secured?** Argon2 hashes, generated JWT secret in ignored local configuration, token expiration and admin-only account provisioning. No source-coded default passwords.

**24. How do frontend and backend communicate?** Relative /api requests with bearer tokens go through Vite's local proxy to FastAPI. Charts are based on actual SQL aggregates.

**25. Can analysts adjudicate alerts?** No; API role checks restrict status updates to admin. Review state still is not a fraud label.

**26. What are the biggest limitations?** Internal retrospective validation, no verified claim labels, heuristic anomaly rules, in-memory preparation, no production security/privacy certification and no native Windows execution yet.

**27. Does a successful unit test prove clinical correctness?** No. Tests verify software behavior and integration, not clinical validity, fairness, prospective performance or legal fraud.

**28. How is reproducibility supported?** Seeded splits/models, source SHA-256 hashes, dependency metadata/lockfile, saved pipelines, documented feature definitions and training commands.
