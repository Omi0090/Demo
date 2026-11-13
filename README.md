# Medicare Integrity
## AI-Powered Healthcare Insurance Fraud Detection and Risk Analytics Using Hybrid Machine Learning and Explainable AI

A **local-only** full-stack final-year project using actual Medicare provider labels and claims. No Docker, cloud services, deployment requirement, invented hospital names, fabricated claims, or claim-level fraud labels.

### Implemented and verified here
- React/Vite/Tailwind dashboard: authentication, overview, provider/claim search and details, alert review, provider and physician analytics, SHAP, model comparison, charts, CSV/PDF exports, responsive dark/light themes.
- FastAPI + JWT roles + SQLAlchemy + real PostgreSQL, 11 application tables and Alembic migrations.
- Four supervised provider models with three-fold stratified training CV and held-out evaluation; selection by training CV average precision.
- Isolation Forest, novelty LOF, robust statistical amount review, and explicit duplicate/repetition/rare-combination rules. Separate provider probability and claim anomaly scores.
- All **558,211** actual claims loaded with **138,556** beneficiaries and **5,410** providers.
- **40 Python tests passed**, including actual PostgreSQL/API/inference/export tests. Chromium browser integration test passed. React production build passed.

**Validation scope:** integrated application successfully run in the Linux development sandbox against PostgreSQL. Native Windows laptop startup has not been executed here. This is a working research implementation, not a clinically validated, production-hardened, or legally adjudicative fraud system. See [limitations](docs/limitations.md).

## Requirements — Windows

Install:
1. Git for Windows.
2. Python **3.11, 64-bit**; enable Add Python to PATH.
3. Node.js **22 LTS** (includes npm).
4. PostgreSQL **16 or 17**, including command-line tools/SQL Shell (psql); remember your installation administrator password. Default port 5432.

Recommended: **8 GB RAM** and at least **6 GB free disk**. Full preparation currently uses in-memory pandas joins. Source CSVs, compressed artifacts, PostgreSQL indexes and its transaction log require additional disk. The complete source dataset was processed successfully on this 4 GB sandbox, but memory on other systems is not guaranteed.

Open PowerShell in this repository. All commands below run from the repository root unless explicitly stated.

## 1. Python environment

```powershell
py -3.11 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend/requirements-lock.txt
```

`requirements-lock.txt` records the versions actually used for training/testing. `requirements.txt` contains supported dependency ranges. Avoid changing numerical-library versions when loading existing joblib artifacts; retrain after upgrades. Only load trusted joblib files.

## 2. Create PostgreSQL database

If `psql` is not on PATH, for PostgreSQL 17:

```powershell
$env:Path += ";C:\Program Files\PostgreSQL\17\bin"
psql -h localhost -U postgres -d postgres
```

Inside psql (SQL commands, not PowerShell):

```sql
CREATE ROLE healthcare LOGIN;
\password healthcare
CREATE DATABASE healthcare_fraud OWNER healthcare;
\q
```

The `\password` prompt asks you to choose the database user's password without placing it in this repository. If your installed version is 16, adjust the PATH accordingly. Skip role/database creation if they already exist.

## 3. Configure secrets

Back in PowerShell:

```powershell
python -m scripts.configure
```

Use host `localhost`, port `5432`, database `healthcare_fraud`, username `healthcare`, and the password you just chose. This creates ignored `.env`, URL-encodes the password, and generates a random JWT secret. No credentials are committed. `.env.example` documents the settings.

## 4. Dataset placement

Obtain the four original training CSVs from [Healthcare Provider Fraud Detection Analysis](https://www.kaggle.com/datasets/rohitrox/healthcare-provider-fraud-detection-analysis). Place them directly in `ml/data/` without changing names:

```text
ml/data/Train-1542865627584.csv
ml/data/Train_Beneficiarydata-1542865627584.csv
ml/data/Train_Inpatientdata-1542865627584.csv
ml/data/Train_Outpatientdata-1542865627584.csv
```

They are already available in this working session, but are deliberately not committed to Git. A fresh clone needs the original files. Never publish patient-level records.

## 5. Inspect, prepare, train, and explain

```powershell
python -m ml.preprocessing.inspect_dataset
python -m ml.preprocessing.prepare
python -m ml.train
```

Outputs:
- `reports/dataset_inspection.json`: actual column/missingness/duplicate/linkage/target inspection.
- `reports/prepared/`: compressed prepared claims/provider features and aggregate `eda.json`.
- `ml/saved_models/provider.joblib`: selected fold-fitted provider pipeline and metadata.
- `ml/saved_models/claim.joblib`: claim preprocessing, IF/LOF models and training-reference rules.
- `ml/saved_models/metrics.json`, `shap.npz`, and prediction files for database ingestion.

Training runs offline, not on each dashboard request. It completed in roughly one minute here after preparation; laptop timings vary. All provider metrics use real labels. Claim anomalies have **no fraud accuracy, precision or recall metrics**, because ground truth does not exist.

Artifacts have already been trained in this session. On a new laptop, run the commands to reproduce them. Optional archive: `python -m scripts.package_models`, creating ignored `reports/trained-models.zip`. It includes derived record IDs; keep it private.

## 6. Migrate and import

```powershell
python -m alembic upgrade head
python -m scripts.ingest
python -m scripts.create_admin
```

Choose your administrator username and a password of at least 10 characters. **There is no fixed default password.** On this sandbox only, a random preview login is stored privately in ignored `reports/local-login.txt`.

Ingestion is transactional and refuses a nonempty claims/provider database; it does not silently append duplicates. It loads patients, providers, claims, normalized codes, model predictions, rules, alerts and model metrics. If an import fails, inspect the error and correct its cause before retrying.

After retraining on the **same records/features**, refresh results with:

```powershell
python -m scripts.refresh_scores
```

**Warning:** this replaces current scores and resets alert review statuses to open. It does not import new claims. Changed source data requires a separately created fresh database and full ingestion; no destructive reset command is run automatically.

## 7. Start backend — terminal 1

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

- Health: http://localhost:8000/api/health
- Swagger/OpenAPI: http://localhost:8000/docs

Use localhost-only binding on your laptop. The sandbox preview binds to 0.0.0.0 only to enable its preview proxy; deployment is not part of this project.

## 8. Start frontend — terminal 2

From a second PowerShell at the repository root:

```powershell
cd frontend
npm ci
npm run dev -- --host 127.0.0.1
```

Open **http://localhost:5173**. Sign in with your administrator account. Browser API calls use relative `/api` URLs; Vite proxies them to the local backend. No separate browser-facing backend URL is required.

## 9. Demonstrate the modules

1. **Overview:** verify real record totals, monthly claim trends and label counts.
2. **Providers:** filter by model risk, select a provider, inspect source label, uncalibrated model probability, training/holdout status and signed SHAP contributions.
3. **Claims:** filter inpatient/outpatient or anomalies, open a claim, inspect codes, indicators and separate provider risk. Click **Re-run inference** to execute both anomaly models from the stored features.
4. **Fraud detection:** inspect rule alerts; admin users can mark reviewed/dismissed. This is a workflow status, not a fraud label.
5. **Provider/physician analytics:** explore computed activity and reimbursement; provider and physician IDs are preserved.
6. **Explainable AI:** inspect global mean absolute SHAP and individual provider contributions.
7. **Model performance:** compare CV/holdout metrics and confusion matrix. The selected model need not have the best holdout score because holdout is not the selection criterion.
8. **Reports:** download provider or suspicious-claim CSV/PDF; exports are bounded to 10,000 records and disclosed in UI.

Admin can create analyst accounts via `POST /api/auth/register` in Swagger using their bearer token. Public self-registration/admin privilege assignment is disabled. Analyst accounts can read/predict/export but cannot create users or modify reviews.

## 10. Tests and frontend build

```powershell
python -m pytest -q
python -m pytest -q --run-integration
cd frontend
npm run build
cd ..
```

The first command skips DB integration; the second requires the ingested actual dataset in PostgreSQL. Integration assertions explicitly verify this dataset's real record counts.

With backend and frontend running, optional browser test:

```powershell
python -m scripts.test_account
cd frontend
npx playwright install chromium
npm run test:e2e
cd ..
python -m scripts.test_account --remove
```

The test creates a temporary account, traverses authenticated pages, checks actual record totals and inference, downloads a CSV, and checks dark/mobile UI. Always remove the test account afterward. On Windows use standard Playwright Chromium; the optional `SANDBOX_CHROMIUM=1` path is only for this sandbox.

## Common errors

| Error | Fix |
|---|---|
| Python/psql/npm not found | Restart PowerShell after installation; use `py -3.11`; add the installed PostgreSQL `bin` directory to PATH. |
| Activation blocked | Use the process-scoped policy above or `.\.venv\Scripts\python.exe` directly. |
| Database connection refused | Start your PostgreSQL Windows service; verify host/port in `.env`. |
| Authentication failed | Confirm DB username/password; rerun `python -m scripts.configure`. API login uses a separate application account. |
| JWT secret validation error | Run configuration; template placeholders are intentionally rejected. |
| Missing files/artifacts | Check exact CSV names, then run inspection, preparation and training in order. |
| Empty database/dashboard | Run Alembic and ingestion against the same DATABASE_URL as the backend. |
| Ingestion refuses existing records | It prevents duplication; refresh scores only for identical imported records or create a fresh DB for a fresh import. |
| Session expired | Sign in again; tokens expire after 60 minutes by default. |
| Port 8000/5173 occupied | Stop the other process. If changing ports, update Vite proxy/CORS settings consistently. |
| Memory error | Close other applications; allow Windows paging or use more RAM. The preparation pipeline is not yet disk-partitioned. |
| Joblib/library version mismatch | Use the lockfile and regenerate artifacts; never trust downloaded pickle files from unknown sources. |
| 403 reviewing alerts | Sign in as admin; analysts are intentionally read-only for review actions. |

## Documentation

- [Architecture and schema](docs/architecture.md)
- [Feature dictionary](docs/features.md)
- [Dataset findings](docs/dataset-findings.md) and [EDA](docs/eda-findings.md)
- [Model comparison](docs/model-comparison.md)
- [API guide](docs/api.md)
- [Testing report](docs/testing-report.md)
- [Limitations and ethics](docs/limitations.md)
- [Project report outline and viva](docs/academic-guide.md)
- [Phase tracker](docs/progress.md)
