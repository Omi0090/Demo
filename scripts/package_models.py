"""Package locally trained artifacts for transfer; never publish sensitive data."""
import zipfile
from pathlib import Path
from ml.train import MODELS
out=Path('reports/trained-models.zip');out.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
    for name in ['provider.joblib','claim.joblib','metrics.json','shap.npz','provider_predictions.csv','claim_predictions.csv.gz']:
        z.write(MODELS/name,arcname=name)
print(out)
