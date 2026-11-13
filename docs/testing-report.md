# Final testing report

## Environment and evidence
Linux development sandbox; Python 3.11 isolated venv; exact Python versions in `backend/requirements-lock.txt`, frontend versions in `frontend/package-lock.json`. Actual PostgreSQL ran via a sandbox-only `pgserver` helper using a local Unix socket. It is a real PostgreSQL server, not an SQLite emulation. Windows instructions use a standard PostgreSQL installation; `pgserver` is not an application requirement.

All four actual source CSVs were inspected, prepared and trained. PostgreSQL ingestion committed the full dataset transactionally. No demonstration fixture is displayed as actual data.

## Executed checks

| Command / check | Result |
|---|---|
| `python -m ml.preprocessing.inspect_dataset` | Passed all four files; no orphan IDs or cross-type ClaimID collisions |
| `python -m ml.preprocessing.prepare` | Passed on 558,211 actual claims; wrote compressed local artifacts and EDA |
| `python -m ml.train` | Four supervised models fitted/tuned/evaluated; IF/LOF trained/scored; selected-model SHAP gate passed |
| `python -m alembic upgrade head` | Passed against actual PostgreSQL |
| `python -m scripts.ingest` | Full transactional import passed |
| `python -m scripts.refresh_scores` | Updated final features, predictions, SHAP, rules and model metrics successfully |
| `python -m pytest -q --run-integration` | **40 passed** |
| `npm run build` | Passed production build |
| Chromium Playwright workspace test | Passed against live Vite + FastAPI + PostgreSQL |
| Fresh-schema migrations | Test created isolated PostgreSQL schema, ran all migrations, asserted 12 tables (11 app + version), cleaned scratch schema |

## Test coverage
- Inspector: missing files, observed schema/linkage contract, duplicate rows across chunks, missing values, IDs and target counts, partial-mode opt-in, empty input and chunk invariance.
- Preprocessing: normal provider aggregates, invalid/missing schema, duplicate ClaimID rejection, malformed/negative dates and nonfinite amounts, code-string preservation, same-day/current-claim exclusion, unknown-date history, retrospective repeated billing candidates.
- ML: all four estimator pipelines fit and joblib round-trip on explicitly synthetic unit fixtures; IF/LOF extreme-vs-normal behavior; transparent repeated/rare/high-cost rule behavior; SHAP additivity.
- Actual PostgreSQL/API: source counts, health, authenticated lists/details, signed explanations, persisted-vs-live provider/claim inference agreement, valid batch, invalid inputs/tokens, unknown IDs, analyst permission denials, all analytics, alerts, CSV/PDF formats and nonempty exports.
- Browser: real login, actual 558,211-claim overview, provider/detail SHAP, claim hybrid analysis and re-inference, all primary navigation pages, CSV download, dark theme and mobile sidebar; no uncaught page errors.

Temporary browser and API test users are removed. A separate randomly generated sandbox local administrator remains for user preview; its password is stored only in ignored `reports/local-login.txt`.

## Resolved issues during implementation
- System Python lacked pytest and rejected global pip installation. Used isolated `.venv` instead.
- Initial browser launch lacked libnspr/libnss in the Linux sandbox. Used the optional Chromium package's bundled libraries; subsequent browser tests passed. This workaround is not required for normal Windows Playwright installation.
- Explicit partial inspection was needed while outpatient data was missing; default strict behavior remains.
- Wider alert reason storage prevents combined rule explanations from being silently truncated.
- Provider monthly features use provider-local date spans, not held-out providers' calendar boundaries.
- Windows dependency markers exclude Linux-only uvloop and NCCL wheels.

## Known warnings and validation limits
Dependency deprecation warnings: Starlette/AnyIO BlockingPortal alias and SciPy L-BFGS-B display options in LogisticRegression. Neither caused failures. These are recorded rather than suppressed.

Unit fixtures are synthetic software tests, not fabricated Medicare training/evaluation data. The held-out provider evaluation is internal and retrospective; see limitations. No claim fraud accuracy is claimed. Native Windows installation, minimum-memory benchmarking, external payer data, exhaustive browser matrix, clinical review, production security and privacy compliance are **not verified**.
