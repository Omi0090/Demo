# Implemented architecture

## Request and data flow

```text
React / Vite / Tailwind / Recharts / Lucide
    │ relative /api, Bearer JWT in sessionStorage
    ▼
Vite development proxy → FastAPI → SQLAlchemy → PostgreSQL
                              │
                              └→ trusted joblib models → recomputed inference

Original CSVs → strict inspection → preparation / EDA → offline training
                                                          │
                                       pipelines / predictions / SHAP
                                                          │
                                   transactional ingestion into PostgreSQL
```

No Docker or deployment layer. On Windows bind both services to 127.0.0.1, access through localhost. The sandbox preview uses 0.0.0.0 and accepts its proxy hostname. The browser never calls sandbox localhost as a separate backend service; Vite proxies relative requests.

## Source layout
- `ml/preprocessing/inspect_dataset.py`: chunked source diagnostics.
- `ml/preprocessing/prepare.py`: validated claims, provider-local aggregates and earlier-date histories.
- `ml/train.py`: supervised comparison, actual-model SHAP, IF/LOF fitting and scoring.
- `ml/claim_detection/rules.py`: explicit training-reference statistical and billing indicators.
- `backend/app/db.py`: settings, SQLAlchemy engine and 11 application ORM tables.
- `backend/app/schemas.py`: typed risk/explanation/hybrid/summary response contracts.
- `backend/app/main.py`: JWT authentication, authorized record queries, analytics, live inference and exports.
- `backend/alembic`: versioned schema initialization and domain constraints.
- `scripts/ingest.py`: PostgreSQL COPY-based transactional import (fallback SQLAlchemy inserts for developer testing only; application validation used PostgreSQL).
- `scripts/refresh_scores.py`: transactional model-result refresh for the same imported records.
- `frontend/src/main.jsx`: connected pages and shared UI components/hooks; `style.css`: Tailwind entry + design system and responsive themes.
- `backend/tests`, `frontend/tests`: unit, database/API, and browser integration tests.

## Database schema

All eleven requested application tables exist, plus Alembic's version table:

| Table | Key and relationships | Main content |
|---|---|---|
| users | integer PK; unique username | Argon2 password hash, constrained admin/analyst role, creation timestamp |
| patients | original BeneID string PK | source patient attributes as JSON; timestamp |
| providers | original Provider string PK | constrained original Yes/No label, aggregate feature JSON; timestamp |
| claims | original ClaimID string PK; indexed provider/patient FKs | dates, type, amount, deductible, physician role IDs, derived feature JSON; timestamp |
| claim_diagnoses | integer PK; indexed claim FK; unique claim-position | string diagnosis code, position 0 reserved for admitting diagnosis |
| claim_procedures | integer PK; indexed claim FK; unique claim-position | string procedure code |
| provider_predictions | provider FK/PK | constrained probability, model version, training/holdout tag, signed SHAP JSON; timestamp |
| claim_anomalies | claim FK/PK | IF/LOF scores, anomaly boolean, indicator JSON, model version; timestamp |
| fraud_alerts | integer PK; indexed claim FK | explicit rule reason, constrained review status; timestamp |
| model_metrics | integer PK; unique model name | actual CV/holdout evaluation JSON; timestamp |
| audit_logs | integer PK; actor FK | action, entity reference, timestamp; no password or patient payload |

Predictions represent the current model snapshot, not a full versioned history. Refresh replaces results; it explicitly resets review statuses. Source clinical attributes vary substantially, so sparse original beneficiary attributes and engineered features use JSON; claim diagnosis/procedure associations remain normalized. Patient data access is not a HIPAA compliance claim.

Migration 001 bootstraps ORM metadata, 002 widens alert reasons, 003 adds guarded domain checks. As schema evolves, maintainers must add explicit migrations rather than relying on `create_all` to modify existing tables.

## Leakage controls and evaluation
Provider ID split is stratified, 80/20, random seed 42. Provider-local retrospective features use only that provider's claims. Population preprocessing is fitted inside three training CV folds. All models use class weighting; XGBoost uses the outer training class ratio. The final pipeline is refit only on training providers; holdout providers are not included in fitting.

Selected model maximizes training CV average precision (non-interpolated PR-AUC convention), not holdout accuracy. Threshold is fixed at 0.5, not tuned on holdout. Source hashes and exact ML library versions are stored in model metadata. The holdout was examined during development and is not a sealed external audit set.

Claim IF/LOF and statistical/rare-pair references fit on a maximum 40,000-claim sample from training providers. Model inputs use earlier-date history (same-day/current claims excluded). Duplicate/repeated-procedure review rules are explicitly retrospective. No claim target is inferred from provider labels, and no combined fraud probability is computed.

SHAP explains the actual selected fitted model on the transformed feature space. TreeExplainer supports trees; LinearExplainer supports logistic regression using a training-only background. Reconstruction of every provider probability must pass an additivity gate (maximum error 1e-4). Contributions retain their output units and baseline.

## Authentication and failure behavior
JWT expiration defaults to 60 minutes. Passwords are Argon2-hashed. Administrator CLI bootstraps an account; only authenticated admins can create analyst accounts or change alert review state. Export and prediction actions are audited. Sensitive configuration is ignored `.env`, generated interactively. Swagger provides bearer-token authorization.

Input bounds, missing IDs, duplicate imports, unavailable models and permissions produce explicit failures. Unexpected exceptions are logged with a generic response; no fake data fallback. Local-only use is mandatory: rate limiting, TLS, token revocation, production access logging, secret rotation, and comprehensive privacy policy are not implemented.

## Scaling
CSV inspection is chunked. Preparation/training still use whole claim tables and joins in RAM. Ingestion uses 5,000-row batches and PostgreSQL COPY inside a transaction. Database indexes support claim/provider/patient/physician lookups and score filters. Dashboard aggregates are SQL-based. Export is capped at 10,000 rows. Monthly source-date strings are ISO validated before import; grouping uses YYYY-MM substrings.
