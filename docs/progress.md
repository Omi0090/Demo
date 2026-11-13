# Phase completion and validation record

| Phase | Implemented work | Validation / qualification |
|---|---|---|
| 1 Architecture | Repository inspection, local-only architecture, source organization | Existing README preserved in Git history; no prior app removed |
| 2 Inspection/preprocessing | All four real CSVs, missingness/duplicates/linkage checks, date/amount validation, provider/claim features | Full dataset executed; imputation/scaling fit in training folds; whole-table preparation uses RAM |
| 3 EDA | True counts, target imbalance, reimbursement percentiles, monthly trends and JSON findings | Generated from all actual records |
| 4 Provider training | LR/tree/RF/XGBoost, CV search, weighting, stratified provider holdout, full metrics, serialization | Executed; see model-comparison.md; internal retrospective evaluation |
| 5 Claim anomalies | IF/novelty LOF, training statistical references, repeated/rare pair rules, separate scores | All actual claims scored; no claim fraud accuracy claims |
| 6 SHAP | Selected actual model, signed local/global contributions, units and additivity gate | Reconstructed probabilities within tolerance |
| 7 PostgreSQL | 11 tables, keys/indexes/checks/timestamps, migrations, transactional COPY ingestion | Real PostgreSQL imported full records; no SQLite substitute used |
| 8 FastAPI | JWT/Argon2/admin-analyst roles, filters/pagination, analytics, existing-record inference, exports, audit | Integration tests passed |
| 9 React | Login/protected workspace, all requested core pages, themes, responsive navigation, states | Production build and Chromium workflow passed |
| 10 Integration | SQL statistics/charts, individual details/SHAP, hybrid scores, live re-inference, downloads | Real backend/db browser flow passed |
| 11 Testing | Unit/ML/DB/API and browser tests | See testing-report.md; not exhaustive |
| 12 Local setup | Exact PowerShell/PostgreSQL/localhost guide; no Docker or deployment | Successfully run on Linux sandbox; native Windows execution remains unverified |
| 13 Documentation | Setup, architecture/schema, features, API, testing, model comparison, limitations, report outline/viva | Documents reflect final implemented scope and evidence |

## Important boundaries
Core integrated research application is implemented and has run successfully with actual PostgreSQL/data. It is not production-certified, clinically validated or verified on the user's Windows laptop. Arbitrary external claim intake, immutable model history, calibration, disk-partitioned preprocessing and production account/security controls are outside current scope. Review these in limitations.md rather than treating them as silently completed features.
