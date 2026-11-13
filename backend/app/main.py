import csv
import io
import json
import logging
from functools import lru_cache
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
import joblib
import jwt
import pandas as pd
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse, Response, JSONResponse
from fastapi import Request
from pydantic import BaseModel, Field, ConfigDict
from pwdlib import PasswordHash
from sqlalchemy import select, func, or_, desc
from sqlalchemy.orm import Session as DBSession
from reportlab.pdfgen import canvas
from backend.app.db import *
from backend.app.schemas import ProviderRecord,HybridResponse,ProviderInference,DashboardSummary
from ml.train import claim_matrix, MODELS

logging.basicConfig(level=logging.INFO)
app=FastAPI(title='Medicare Integrity API',version='1.0.0',description='Provider risk and unverified claim anomalies. Local research use only.')
app.add_middleware(CORSMiddleware,allow_origins=[settings.frontend_origin],allow_methods=['*'],allow_headers=['*'])
security=HTTPBearer(); passwords=PasswordHash.recommended()

@lru_cache(maxsize=4)
def _cached_model(name,modified):
    return joblib.load(MODELS/name)

def load_model(name):
    path=MODELS/name
    if not path.exists(): raise HTTPException(409,'Model artifact unavailable; run training')
    return _cached_model(name,path.stat().st_mtime_ns)


def db():
    with Session() as s: yield s

def current(credentials: HTTPAuthorizationCredentials=Depends(security),s: DBSession=Depends(db)):
    try:
        payload=jwt.decode(credentials.credentials,settings.jwt_secret,algorithms=['HS256'])
        user=s.get(User,int(payload['sub']))
        if not user: raise ValueError()
        return user
    except (jwt.PyJWTError,ValueError,KeyError): raise HTTPException(401,'Invalid or expired token')

def admin(user=Depends(current)):
    if user.role!='admin': raise HTTPException(403,'Administrator permission required')
    return user

class Credentials(BaseModel):
    username: str=Field(min_length=3,max_length=80,pattern=r'^[a-zA-Z0-9_.@-]+$')
    password: str=Field(min_length=10,max_length=128)
class TokenResponse(BaseModel):
    access_token: str
    token_type: str='bearer'
class Identity(BaseModel):
    id:int; username:str; role:str
    model_config=ConfigDict(from_attributes=True)
class ProviderInput(BaseModel): provider_id:str=Field(min_length=1,max_length=40)
class ClaimInput(BaseModel): claim_id:str=Field(min_length=1,max_length=40)
class BatchInput(BaseModel): claim_ids:list[str]=Field(min_length=1,max_length=100)

@app.get('/api/health')
def health(s:DBSession=Depends(db)):
    s.execute(select(1)); return {'status':'ok','models_ready':(MODELS/'provider.joblib').exists() and (MODELS/'claim.joblib').exists()}

@app.post('/api/auth/login',response_model=TokenResponse)
def login(body:Credentials,s:DBSession=Depends(db)):
    user=s.scalar(select(User).where(User.username==body.username))
    # Verify a dummy hash for absent accounts to avoid a cheap username timing leak.
    valid=passwords.verify(body.password,user.password_hash if user else DUMMY_HASH)
    if not user or not valid: raise HTTPException(401,'Invalid username or password')
    s.add(Audit(actor_id=user.id,action='login',entity='session')); s.commit()
    return {'access_token':jwt.encode({'sub':str(user.id),'exp':datetime.now(timezone.utc)+timedelta(minutes=settings.jwt_expire_minutes)},settings.jwt_secret,algorithm='HS256')}
DUMMY_HASH=passwords.hash('not-a-real-login-password')

@app.post('/api/auth/register',response_model=Identity,status_code=201)
def register(body:Credentials,user=Depends(admin),s:DBSession=Depends(db)):
    if s.scalar(select(User).where(User.username==body.username)): raise HTTPException(409,'Username already exists')
    created=User(username=body.username,password_hash=passwords.hash(body.password),role='analyst')
    s.add(created); s.flush(); s.add(Audit(actor_id=user.id,action='create_analyst',entity=str(created.id))); s.commit(); s.refresh(created)
    return created
@app.get('/api/auth/me',response_model=Identity)
def me(user=Depends(current)): return user

@app.get('/api/dashboard/summary',response_model=DashboardSummary)
def summary(user=Depends(current),s:DBSession=Depends(db)):
    count=lambda model:s.scalar(select(func.count()).select_from(model))
    return dict(providers=count(Provider),patients=count(Patient),claims=count(Claim),
        labeled_potential_fraud=s.scalar(select(func.count()).select_from(Provider).where(Provider.observed_label=='Yes')),
        high_risk_providers=s.scalar(select(func.count()).select_from(ProviderPrediction).where(ProviderPrediction.probability>=.5)),
        anomalous_claims=s.scalar(select(func.count()).select_from(ClaimAnomaly).where(ClaimAnomaly.anomalous.is_(True))),
        reimbursement=s.scalar(select(func.coalesce(func.sum(Claim.amount),0))),alerts=count(Alert))
@app.get('/api/dashboard/claim-trends')
def trends(user=Depends(current),s:DBSession=Depends(db)):
    month=func.substr(Claim.start_date,1,7)
    return [dict(month=m,claims=n,reimbursement=a) for m,n,a in s.execute(select(month,func.count(),func.sum(Claim.amount)).group_by(month).order_by(month))]
@app.get('/api/dashboard/fraud-distribution')
def distribution(user=Depends(current),s:DBSession=Depends(db)):
    labels=[dict(name=k,value=v) for k,v in s.execute(select(Provider.observed_label,func.count()).group_by(Provider.observed_label))]
    anomalies=[dict(name='Anomalous' if k else 'Normal',value=v) for k,v in s.execute(select(ClaimAnomaly.anomalous,func.count()).group_by(ClaimAnomaly.anomalous))]
    types=[dict(name=k,value=v) for k,v in s.execute(select(Claim.claim_type,func.count()).group_by(Claim.claim_type))]
    return dict(provider_labels=labels,claim_anomalies=anomalies,claim_types=types)

def get_provider(pid,s):
    p=s.get(Provider,pid)
    if not p: raise HTTPException(404,'Provider not found')
    risk=s.get(ProviderPrediction,pid)
    return dict(id=p.id,observed_label=p.observed_label,features=p.features,risk=None if not risk else dict(probability=risk.probability,classification='Potentially Fraudulent' if risk.probability>=.5 else 'Non-Fraudulent',model_version=risk.model_version,split=risk.split,explanation=risk.explanation,note='Uncalibrated provider probability; not a confirmed finding of fraud.'))
@app.get('/api/providers')
def providers(search:str='',page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),risk:Literal['all','high','low']='all',user=Depends(current),s:DBSession=Depends(db)):
    q=select(Provider.id,Provider.observed_label,Provider.features,ProviderPrediction.probability).outerjoin(ProviderPrediction).where(Provider.id.ilike(f'%{search}%'))
    if risk=='high': q=q.where(ProviderPrediction.probability>=.5)
    if risk=='low': q=q.where(ProviderPrediction.probability<.5)
    total=s.scalar(select(func.count()).select_from(q.subquery()))
    return dict(total=total,page=page,items=[dict(id=a,observed_label=b,features=c,probability=d) for a,b,c,d in s.execute(q.order_by(desc(ProviderPrediction.probability)).offset((page-1)*page_size).limit(page_size))])
@app.get('/api/providers/{provider_id}',response_model=ProviderRecord)
def provider(provider_id:str,user=Depends(current),s:DBSession=Depends(db)): return get_provider(provider_id,s)
@app.get('/api/providers/{provider_id}/risk',response_model=ProviderRecord)
@app.get('/api/ml/explanations/{provider_id}',response_model=ProviderRecord)
def provider_risk(provider_id:str,user=Depends(current),s:DBSession=Depends(db)): return get_provider(provider_id,s)


def claim_dict(c):
    return dict(id=c.id,provider_id=c.provider_id,patient_id=c.patient_id,claim_type=c.claim_type,start_date=c.start_date,end_date=c.end_date,amount=c.amount,deductible=c.deductible,attending=c.attending,operating=c.operating,other=c.other,features=c.features)
@app.get('/api/claims')
def claims(search:str='',provider_id:str|None=None,claim_type:Literal['inpatient','outpatient']|None=None,anomalous:bool|None=None,min_amount:float|None=None,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),user=Depends(current),s:DBSession=Depends(db)):
    q=select(Claim,ClaimAnomaly).outerjoin(ClaimAnomaly).where(or_(Claim.id.ilike(f'%{search}%'),Claim.patient_id.ilike(f'%{search}%')))
    if provider_id: q=q.where(Claim.provider_id==provider_id)
    if claim_type: q=q.where(Claim.claim_type==claim_type)
    if anomalous is not None: q=q.where(ClaimAnomaly.anomalous==anomalous)
    if min_amount is not None: q=q.where(Claim.amount>=min_amount)
    total=s.scalar(select(func.count()).select_from(q.subquery()))
    return dict(total=total,page=page,items=[dict(**claim_dict(c),anomalous=a.anomalous if a else None) for c,a in s.execute(q.order_by(Claim.id).offset((page-1)*page_size).limit(page_size))])
@app.get('/api/providers/{provider_id}/claims')
def provider_claims(provider_id:str,page:int=Query(1,ge=1),user=Depends(current),s:DBSession=Depends(db)):
    get_provider(provider_id,s)
    return claims(provider_id=provider_id,page=page,page_size=20,user=user,s=s)
@app.get('/api/claims/{claim_id}')
def claim_detail(claim_id:str,user=Depends(current),s:DBSession=Depends(db)):
    c=s.get(Claim,claim_id)
    if not c: raise HTTPException(404,'Claim not found')
    return dict(**claim_dict(c),diagnoses=[{'position':d.position,'code':d.code} for d in s.scalars(select(Diagnosis).where(Diagnosis.claim_id==claim_id))],procedures=[{'position':d.position,'code':d.code} for d in s.scalars(select(Procedure).where(Procedure.claim_id==claim_id))])

def hybrid(cid,s):
    c=s.get(Claim,cid)
    if not c: raise HTTPException(404,'Claim not found')
    a=s.get(ClaimAnomaly,cid)
    if not a: raise HTTPException(409,'No claim model result; run training and ingestion')
    return dict(claim_id=cid,result='Anomalous' if a.anomalous else 'Normal',isolation_score=a.isolation_score,lof_score=a.lof_score,indicators=a.indicators,provider=get_provider(c.provider_id,s)['risk'],note='Unsupervised review signal, not confirmed fraud or a calibrated fraud probability.')
@app.get('/api/claims/{claim_id}/anomaly',response_model=HybridResponse)
def anomaly(claim_id:str,user=Depends(current),s:DBSession=Depends(db)): return hybrid(claim_id,s)
@app.post('/api/predict/provider',response_model=ProviderInference)
def predict_provider(body:ProviderInput,user=Depends(current),s:DBSession=Depends(db)):
    p=get_provider(body.provider_id,s)
    if not (MODELS/'provider.joblib').exists(): raise HTTPException(409,'Provider model unavailable')
    bundle=load_model('provider.joblib'); x=pd.DataFrame([p['features']]).reindex(columns=bundle['features'])
    probability=float(bundle['pipeline'].predict_proba(x)[0,1])
    s.add(Audit(actor_id=user.id,action='predict_provider',entity=body.provider_id)); s.commit()
    return dict(**p,recomputed_probability=probability)
@app.post('/api/predict/claim',response_model=HybridResponse)
def predict_claim(body:ClaimInput,user=Depends(current),s:DBSession=Depends(db)):
    c=s.get(Claim,body.claim_id)
    if not c: raise HTTPException(404,'Claim not found')
    if not (MODELS/'claim.joblib').exists(): raise HTTPException(409,'Claim model unavailable')
    bundle=load_model('claim.joblib')
    frame=pd.DataFrame([dict(c.features,claim_type=c.claim_type,InscClaimAmtReimbursed=c.amount,DeductibleAmtPaid=c.deductible)])
    z=bundle['preprocessing'].transform(claim_matrix(frame))
    result=hybrid(c.id,s)
    result['isolation_score']=float(-bundle['isolation'].score_samples(z)[0]); result['lof_score']=float(-bundle['lof'].score_samples(z)[0])
    s.add(Audit(actor_id=user.id,action='predict_claim',entity=c.id)); s.commit()
    return result
@app.post('/api/predict/batch',response_model=list[HybridResponse])
def batch(body:BatchInput,user=Depends(current),s:DBSession=Depends(db)):
    return [predict_claim(ClaimInput(claim_id=cid),user,s) for cid in body.claim_ids]
@app.get('/api/ml/model-metrics')
def metrics(user=Depends(current),s:DBSession=Depends(db)):
    return [m.payload for m in s.scalars(select(Metric))]
@app.get('/api/ml/global-importance')
def importance(user=Depends(current),s:DBSession=Depends(db)):
    import numpy as np
    path=MODELS/'shap.npz'
    if not path.exists(): raise HTTPException(409,'SHAP artifact unavailable')
    metadata=json.loads((MODELS/'metrics.json').read_text()); values=np.load(path)['values']
    return dict(units=metadata['shap_units'],features=sorted([dict(feature=k,importance=float(v)) for k,v in zip(metadata['features'],np.abs(values).mean(axis=0))],key=lambda x:-x['importance']))
@app.get('/api/alerts')
def alerts(page:int=Query(1,ge=1),user=Depends(current),s:DBSession=Depends(db)):
    return dict(total=s.scalar(select(func.count()).select_from(Alert)),items=[dict(id=a.id,claim_id=a.claim_id,reason=a.reason,status=a.status) for a in s.scalars(select(Alert).order_by(Alert.id).offset((page-1)*20).limit(20))])
class Review(BaseModel): status:Literal['open','reviewed','dismissed']
@app.patch('/api/alerts/{alert_id}')
def review(alert_id:int,body:Review,user=Depends(admin),s:DBSession=Depends(db)):
    a=s.get(Alert,alert_id)
    if not a: raise HTTPException(404,'Alert not found')
    a.status=body.status; s.add(Audit(actor_id=user.id,action='review_alert',entity=str(alert_id))); s.commit(); return {'status':a.status}
@app.get('/api/analytics/providers')
def comparison(user=Depends(current),s:DBSession=Depends(db)):
    return [dict(provider_id=p,claims=n,reimbursement=a,patients=b,average=m) for p,n,a,b,m in s.execute(select(Claim.provider_id,func.count(),func.sum(Claim.amount),func.count(func.distinct(Claim.patient_id)),func.avg(Claim.amount)).group_by(Claim.provider_id).order_by(desc(func.sum(Claim.amount))).limit(30))]
@app.get('/api/analytics/physicians')
def physicians(search:str='',page:int=Query(1,ge=1),user=Depends(current),s:DBSession=Depends(db)):
    from sqlalchemy import union
    # UNION deduplicates a physician appearing in multiple roles on the same claim.
    association=union(*[select(Claim.id.label('claim_id'),field.label('physician')).where(field.is_not(None)) for field in [Claim.attending,Claim.operating,Claim.other]]).subquery()
    from sqlalchemy import case
    reference=load_model('claim.joblib')['high_amount']
    high_count=func.sum(case((Claim.amount>reference,1),else_=0))
    q=select(association.c.physician,func.count(),func.sum(Claim.amount),func.count(func.distinct(Claim.provider_id)),high_count).join(Claim,Claim.id==association.c.claim_id).where(association.c.physician.ilike(f'%{search}%')).group_by(association.c.physician)
    total=s.scalar(select(func.count()).select_from(q.subquery()))
    return dict(total=total,items=[dict(physician=p,claims=n,reimbursement=a,providers=b,high_amount_claims=h) for p,n,a,b,h in s.execute(q.order_by(desc(func.count())).offset((page-1)*20).limit(20))])

@app.get('/api/reports/{kind}')
def report(kind:Literal['providers','claims'],format:Literal['csv','pdf']='csv',user=Depends(current),s:DBSession=Depends(db)):
    # Exports are explicitly bounded to protect laptop memory. UI discloses cap.
    if kind=='providers':
        headers=['provider_id','observed_label','model_probability']
        rows=list(s.execute(select(Provider.id,Provider.observed_label,ProviderPrediction.probability).outerjoin(ProviderPrediction).order_by(Provider.id).limit(10000)))
    else:
        headers=['claim_id','provider_id','amount','isolation_score','lof_score','anomalous']
        rows=list(s.execute(select(Claim.id,Claim.provider_id,Claim.amount,ClaimAnomaly.isolation_score,ClaimAnomaly.lof_score,ClaimAnomaly.anomalous).join(ClaimAnomaly).where(ClaimAnomaly.anomalous.is_(True)).order_by(Claim.id).limit(10000)))
    s.add(Audit(actor_id=user.id,action='export',entity=kind)); s.commit()
    if format=='pdf':
        buf=io.BytesIO(); pdf=canvas.Canvas(buf); y=800
        pdf.setFont('Helvetica',8); pdf.drawString(30,y,'Medicare Integrity: '+kind+' | Review signals, not confirmed fraud'); y-=20
        for row in [headers]+[list(r) for r in rows]:
            if y<40: pdf.showPage(); pdf.setFont('Helvetica',8); y=800
            pdf.drawString(30,y,' | '.join(str(x) for x in row)[:140]); y-=12
        pdf.save(); content=buf.getvalue(); media='application/pdf'
    else:
        buf=io.StringIO(); writer=csv.writer(buf); writer.writerow(headers)
        for row in rows: writer.writerow([("'"+v if isinstance(v,str) and v.startswith(('=','+','-','@')) else v) for v in row])
        content=buf.getvalue().encode(); media='text/csv'
    return Response(content,media_type=media,headers={'Content-Disposition':f'attachment; filename="{kind}.{format}"'})

@app.get('/api/analytics/distributions')
def score_distributions(user=Depends(current),s:DBSession=Depends(db)):
    from sqlalchemy import case
    amount_bucket=case((Claim.amount==0,'0'),(Claim.amount<=100,'1–100'),(Claim.amount<=1000,'101–1,000'),(Claim.amount<=10000,'1,001–10,000'),else_='>10,000')
    anomaly_bucket=func.floor(ClaimAnomaly.isolation_score*20)/20
    provider_bucket=case((ProviderPrediction.probability<.2,'0–20%'),(ProviderPrediction.probability<.5,'20–50%'),(ProviderPrediction.probability<.8,'50–80%'),else_='80–100%')
    return dict(amounts=[dict(bucket=k,count=n) for k,n in s.execute(select(amount_bucket,func.count()).group_by(amount_bucket))],anomaly_scores=[dict(bucket=round(float(k),2),count=n) for k,n in s.execute(select(anomaly_bucket,func.count()).group_by(anomaly_bucket).order_by(anomaly_bucket))],provider_risk=[dict(name=k,value=n) for k,n in s.execute(select(provider_bucket,func.count()).group_by(provider_bucket))])

@app.exception_handler(Exception)
async def unexpected_error(request:Request,exc:Exception):
    logging.getLogger(__name__).exception("Unhandled API error: %s",request.url.path,exc_info=exc)
    return JSONResponse(status_code=500,content={"detail":"Internal server error. Check backend logs; no data was silently substituted."})
