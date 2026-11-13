"""Transactional first ingestion. Refuses nonempty claims to prevent duplication."""
import json
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import pandas as pd
from sqlalchemy import select,func,insert
from sqlalchemy.types import JSON
from psycopg.types.json import Jsonb
from backend.app.db import *
from ml.preprocessing.inspect_dataset import FILES
from ml.train import MODELS,PREPARED,CLAIM_FEATURES

ROOT=Path(__file__).resolve().parents[1]
def clean(value):
    if value is None or pd.isna(value): return None
    return value.item() if isinstance(value,np.generic) else value

def write(s,model,rows):
    if not rows: return
    if 'created_at' in model.__table__.columns:
        for r in rows: r['created_at']=datetime.now(timezone.utc)
    if s.bind.dialect.name=='postgresql':
        cols=list(rows[0]); jsoncols={c.name for c in model.__table__.columns if isinstance(c.type,JSON)}
        with s.connection().connection.driver_connection.cursor() as cur:
            with cur.copy(f'COPY {model.__tablename__} ({",".join(cols)}) FROM STDIN') as cp:
                for r in rows: cp.write_row(tuple(Jsonb(r[k]) if k in jsoncols else r[k] for k in cols))
    else: s.execute(insert(model),rows)

def ingest():
    meta=json.loads((MODELS/'metrics.json').read_text()); version=meta['best_model']+'-42-v1'
    with Session.begin() as s:
        if s.scalar(select(func.count()).select_from(Claim)): raise ValueError('Claims already loaded; refusing duplicate ingestion')
        if s.scalar(select(func.count()).select_from(Provider)): raise ValueError('Providers already loaded; use a fresh database')
        providers=pd.read_csv(PREPARED/'provider_features.csv.gz',dtype={'Provider':'string'})
        predictions=pd.read_csv(MODELS/'provider_predictions.csv')
        shap=np.load(MODELS/'shap.npz')['values']
        write(s,Provider,[dict(id=r['Provider'],observed_label=r['PotentialFraud'],features={k:clean(v) for k,v in r.items() if k not in ['Provider','PotentialFraud']}) for r in providers.to_dict('records')])
        write(s,ProviderPrediction,[dict(provider_id=r.Provider,probability=float(r.probability),model_version=version,split=r.split,explanation={'base':meta['shap_base'],'units':meta['shap_units'],'contributions':[{'feature':k,'contribution':float(v),'value':clean(providers.iloc[i][k])} for k,v in sorted(zip(meta['features'],shap[i]),key=lambda t:-abs(t[1]))]}) for i,r in enumerate(predictions.itertuples(index=False))])
        for chunk in pd.read_csv(ROOT/'ml/data'/FILES['beneficiaries'],dtype='string',chunksize=5000):
            write(s,Patient,[dict(id=r['BeneID'],attributes={k:clean(v) for k,v in r.items() if k!='BeneID'}) for r in chunk.to_dict('records')])
        print('Loaded reference tables',flush=True)
        for chunk in pd.read_csv(PREPARED/'claims_prepared.csv.gz',dtype='string',chunksize=5000):
            rows=[]; diagnoses=[]; procedures=[]
            for r in chunk.to_dict('records'):
                numeric=lambda key: float(r[key]) if key in r and pd.notna(r[key]) else None
                rows.append(dict(id=r['ClaimID'],provider_id=r['Provider'],patient_id=r['BeneID'],claim_type=r['claim_type'],start_date=r['ClaimStartDt'][:10],end_date=r['ClaimEndDt'][:10],amount=numeric('InscClaimAmtReimbursed'),deductible=numeric('DeductibleAmtPaid'),attending=clean(r.get('AttendingPhysician')),operating=clean(r.get('OperatingPhysician')),other=clean(r.get('OtherPhysician')),features={k:numeric(k) for k in CLAIM_FEATURES if k not in ['InscClaimAmtReimbursed','DeductibleAmtPaid','is_inpatient']}))
                for k,v in r.items():
                    if k.startswith('ClmDiagnosisCode_') and pd.notna(v): diagnoses.append(dict(claim_id=r['ClaimID'],position=int(k.rsplit('_',1)[1]),code=v))
                    if k.startswith('ClmProcedureCode_') and pd.notna(v): procedures.append(dict(claim_id=r['ClaimID'],position=int(k.rsplit('_',1)[1]),code=v))
                if pd.notna(r.get('ClmAdmitDiagnosisCode')): diagnoses.append(dict(claim_id=r['ClaimID'],position=0,code=r['ClmAdmitDiagnosisCode']))
            write(s,Claim,rows); write(s,Diagnosis,diagnoses); write(s,Procedure,procedures)
        print('Loaded claims and clinical codes',flush=True)
        for chunk in pd.read_csv(MODELS/'claim_predictions.csv.gz',chunksize=5000):
            anomalies=[]; alerts=[]
            for r in chunk.itertuples(index=False):
                indicators=json.loads(r.indicators)
                anomalies.append(dict(claim_id=r.ClaimID,isolation_score=r.isolation_score,lof_score=r.lof_score,anomalous=bool(r.anomalous),indicators=indicators,model_version='IF-LOF-42-v1'))
                if indicators: alerts.append(dict(claim_id=r.ClaimID,reason='; '.join(indicators),status='open'))
            write(s,ClaimAnomaly,anomalies); write(s,Alert,alerts)
        write(s,Metric,[dict(model_name=m['model'],payload=dict(m,selected=m['model']==meta['best_model'],selection=meta['selection'],shap_additivity_error=meta['shap_max_additivity_error'])) for m in meta['metrics']])
    print('Ingestion committed',flush=True)

if __name__=='__main__': ingest()
