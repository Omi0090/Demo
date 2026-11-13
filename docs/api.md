# API guide

Base: `http://localhost:8000/api`; interactive schema: `/docs`; raw schema: `/openapi.json`.

All routes except login and health require `Authorization: Bearer <access_token>`. Obtain token by posting JSON username/password to `/api/auth/login`. Swagger accepts the token through **Authorize** (HTTP Bearer; paste token, not the word Bearer).

| Method | Route | Purpose |
|---|---|---|
| POST | /auth/login | Authenticate; returns token and type |
| POST | /auth/register | Admin creates analyst; caller cannot select role |
| GET | /auth/me | Current identity and role |
| GET | /health | PostgreSQL connectivity and artifact presence |
| GET | /dashboard/summary | Actual source counts, risk/anomaly counts, total amount |
| GET | /dashboard/claim-trends | Monthly claim count/reimbursement |
| GET | /dashboard/fraud-distribution | Observed labels, anomaly results, claim types |
| GET | /providers | Search/risk filter and pagination |
| GET | /providers/{id} | Provider features, observed label, current model risk and SHAP |
| GET | /providers/{id}/claims | Paginated associated claims |
| GET | /providers/{id}/risk | Provider details with separate typed risk |
| GET | /claims | Search/type/anomaly/provider/amount filters and pagination |
| GET | /claims/{id} | Original claim and normalized codes |
| GET | /claims/{id}/anomaly | Stored hybrid result |
| POST | /predict/provider | Recompute selected provider inference for existing provider_id |
| POST | /predict/claim | Re-run IF/LOF for an existing claim_id; return persisted explicit rule evidence |
| POST | /predict/batch | Re-run up to 100 existing claim IDs |
| GET | /ml/model-metrics | Actual four-model comparison with selected marker |
| GET | /ml/explanations/{id} | Individual provider features and SHAP contributions |
| GET | /ml/global-importance | Mean absolute SHAP, descriptive across all provider records |
| GET | /alerts | Paginated rule-triggered review queue |
| PATCH | /alerts/{id} | Admin-only open/reviewed/dismissed workflow |
| GET | /analytics/providers | Top 30 provider reimbursement/volume comparison |
| GET | /analytics/physicians | Search/paginated all-role physician associations |
| GET | /analytics/distributions | Amount buckets, IF score histogram, provider risk bins |
| GET | /reports/providers | CSV or PDF, bounded to 10,000 records |
| GET | /reports/claims | Anomalous claim CSV or PDF, bounded to 10,000 records |

Provider filters: `search`, `risk=all|high|low`, `page>=1`, `page_size=1..100`. Claim filters: `search` (ClaimID or BeneID), `provider_id`, `claim_type=inpatient|outpatient`, `anomalous=true|false`, `min_amount`, `page`, `page_size`. Alerts and physicians have 20-row pages. Reports accept `format=csv|pdf`; suspicious-claim exports include anomalous candidates and omit normal claims.

Prediction JSON examples (replace IDs with real listing IDs):

```json
{"provider_id":"PRV51001"}
```
```json
{"claim_id":"CLM110011"}
```
```json
{"claim_ids":["CLM110011"]}
```

The inference endpoints operate on existing validated records, not arbitrary new manually entered medical claims. New-record ingestion requires offline inspection/preparation and a fresh import; a generalized external insurer ingestion API is not implemented.

Hybrid result includes `result`, `isolation_score`, `lof_score`, explicit indicators and nested **separate** provider risk/probability/explanation. No `claim_fraud_probability` is returned. Provider explanations specify log-odds/probability units; signs are not calibrated percentages.

Common statuses: 200 success; 201 analyst created; 401 invalid/expired login; 403 missing bearer token or insufficient role (HTTPBearer may use 403); 404 unknown ID; 409 existing username or unavailable model result; 422 schema/range validation; 500 logged unexpected failure. No fallback fake records.
