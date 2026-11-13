# Actual provider model comparison

Selected model: **XGBoost**, maximum training three-fold CV average precision.

Split: 4,328 training providers / 1,082 holdout; seed 42. Positive class Yes. Threshold 0.5. PR-AUC convention: sklearn average precision, not trapezoidal integration.

| Model | CV AP | Accuracy | Precision | Recall | F1 | ROC-AUC | Holdout AP |
|---|---:|---:|---:|---:|---:|---:|---:|
| Logistic Regression | 0.6840 | 0.8706 | 0.4118 | 0.9010 | 0.5652 | 0.9599 | 0.7551 |
| Decision Tree | 0.5304 | 0.8706 | 0.4049 | 0.8218 | 0.5425 | 0.8735 | 0.6086 |
| Random Forest | 0.6772 | 0.9436 | 0.7326 | 0.6238 | 0.6738 | 0.9599 | 0.7552 |
| XGBoost | 0.6904 | 0.8854 | 0.4428 | 0.8812 | 0.5894 | 0.9625 | 0.7697 |

## Selected model evidence

Confusion matrix (rows actual No/Yes, columns predicted No/Yes): `[[869, 112], [12, 89]]`.
SHAP units: `log_odds`. Maximum probability reconstruction error: `2.9802322e-07` (gate: 1e-4).

Grid searches (all use median imputation, scaling, training CV):
- Logistic Regression: chosen `{'model__C': 0.1}`.
- Decision Tree: chosen `{'model__max_depth': 8, 'model__min_samples_leaf': 5}`.
- Random Forest: chosen `{'model__max_depth': None, 'model__min_samples_leaf': 2}`.
- XGBoost: chosen `{'model__max_depth': 3}`.

Candidate grids: logistic C [0.1,1]; tree max_depth [4,8], min_samples_leaf 5; RF max_depth [8,None], min_samples_leaf 2, 160 trees; XGBoost max_depth [3,5], 180 trees, learning_rate .06. Models use class weighting.

## Interpretation

A high-recall model can create many false-positive reviews. Do not use this classifier to deny claims or label actual institutions as confirmed fraudulent. Provider probabilities are not calibrated. Holdout scores are internal retrospective estimates; the split was inspected during iterative development and is not an independent external audit. Source fingerprints and exact library versions are retained in metrics.json.

## Claim module

IF and novelty LOF use up to 40,000 sampled training-provider claims; contamination 0.05; IF 120 trees; LOF 25 neighbors. Numeric preprocessing fits only the reference sample. Combined anomaly flag is an OR across model thresholds and explicit rule evidence, not a calibrated hybrid fraud probability. Rule thresholds and scoring semantics are documented separately. There are no verified claim labels, so no claim-fraud precision/recall metrics are reported.
