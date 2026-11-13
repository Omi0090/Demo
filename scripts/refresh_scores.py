"""Refresh persisted scores after training, without reimporting clinical records."""
import json
import numpy as np
import pandas as pd
from sqlalchemy import delete,update
from scripts.ingest import write,MODELS,PREPARED,clean
from backend.app.db import Session,ProviderPrediction,ClaimAnomaly,Alert,Metric,Provider

def main():
    meta=json.loads((MODELS/'metrics.json').read_text())
    providers=pd.read_csv(PREPARED/'provider_features.csv.gz',dtype={'Provider':'string'})
    predictions=pd.read_csv(MODELS/'provider_predictions.csv')
    shap=np.load(MODELS/'shap.npz')['values']
    with Session.begin() as s:
        for r in providers.to_dict('records'):
            s.execute(update(Provider).where(Provider.id==r['Provider']).values(features={k:clean(v) for k,v in r.items() if k not in ['Provider','PotentialFraud']}))
        for model in [Alert,ClaimAnomaly,ProviderPrediction,Metric]:s.execute(delete(model))
        write(s,ProviderPrediction,[dict(provider_id=r.Provider,probability=float(r.probability),model_version=meta['best_model']+'-42-v1',split=r.split,explanation={'base':meta['shap_base'],'units':meta['shap_units'],'contributions':[{'feature':k,'contribution':float(v),'value':clean(providers.iloc[i][k])} for k,v in sorted(zip(meta['features'],shap[i]),key=lambda t:-abs(t[1]))]}) for i,r in enumerate(predictions.itertuples(index=False))])
        for chunk in pd.read_csv(MODELS/'claim_predictions.csv.gz',chunksize=5000):
            records=[];alerts=[]
            for r in chunk.itertuples(index=False):
                indicators=json.loads(r.indicators)
                records.append(dict(claim_id=r.ClaimID,isolation_score=r.isolation_score,lof_score=r.lof_score,anomalous=bool(r.anomalous),indicators=indicators,model_version='IF-LOF-42-v1'))
                if indicators:alerts.append(dict(claim_id=r.ClaimID,reason='; '.join(indicators),status='open'))
            write(s,ClaimAnomaly,records);write(s,Alert,alerts)
        write(s,Metric,[dict(model_name=m['model'],payload=dict(m,selected=m['model']==meta['best_model'],selection=meta['selection'],shap_additivity_error=meta['shap_max_additivity_error'])) for m in meta['metrics']])
    print('Scores refreshed. Alert review states reset to open.')
if __name__=='__main__':main()
