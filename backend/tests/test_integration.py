"""Opt-in tests against the locally ingested actual PostgreSQL database.

Temporary test accounts are removed; production records are read only.
Run: python -m pytest backend/tests/test_integration.py --run-integration
"""
import uuid
import pytest
from fastapi.testclient import TestClient

@pytest.fixture(scope='module')
def client(request):
    if not request.config.getoption('--run-integration'):
        pytest.skip('Requires actual ingested PostgreSQL; pass --run-integration')
    from backend.app.main import app
    return TestClient(app)

@pytest.fixture(scope='module')
def auth(client):
    from backend.app.db import Session,User,Audit
    from pwdlib import PasswordHash
    from sqlalchemy import delete
    name='test_'+uuid.uuid4().hex[:12]; password=uuid.uuid4().hex
    with Session.begin() as s:
        u=User(username=name,password_hash=PasswordHash.recommended().hash(password),role='analyst');s.add(u);s.flush();uid=u.id
    r=client.post('/api/auth/login',json={'username':name,'password':password})
    assert r.status_code==200,r.text
    yield {'Authorization':'Bearer '+r.json()['access_token']}
    with Session.begin() as s:
        s.execute(delete(Audit).where(Audit.actor_id==uid));s.execute(delete(User).where(User.id==uid))

def test_health(client): assert client.get('/api/health').json()['status']=='ok'
def test_protected(client): assert client.get('/api/dashboard/summary').status_code in [401,403]
def test_summary_actual_data(client,auth):
    d=client.get('/api/dashboard/summary',headers=auth).json()
    assert d['claims']==558211 and d['providers']==5410 and d['patients']==138556

def test_provider_detail_and_shap(client,auth):
    r=client.get('/api/providers?page_size=1',headers=auth)
    assert r.status_code==200,r.text
    pid=r.json()['items'][0]['id']
    detail=client.get('/api/providers/'+pid,headers=auth).json()
    assert detail['risk']['explanation']['contributions']
    p=client.post('/api/predict/provider',headers=auth,json={'provider_id':pid})
    assert p.status_code==200,p.text
    assert abs(p.json()['recomputed_probability']-detail['risk']['probability'])<1e-6

def test_claim_hybrid_prediction(client,auth):
    r=client.get('/api/claims?page_size=1',headers=auth);assert r.status_code==200,r.text
    cid=r.json()['items'][0]['id']
    d=client.get('/api/claims/'+cid,headers=auth);assert d.status_code==200,d.text
    a=client.get('/api/claims/'+cid+'/anomaly',headers=auth).json()
    p=client.post('/api/predict/claim',headers=auth,json={'claim_id':cid})
    assert p.status_code==200,p.text
    assert abs(p.json()['isolation_score']-a['isolation_score'])<1e-6
    assert 'provider' in a and 'probability' not in {k:a[k] for k in a if k!='provider'}

@pytest.mark.parametrize('path',['/dashboard/claim-trends','/dashboard/fraud-distribution','/analytics/providers','/analytics/physicians','/ml/model-metrics','/ml/global-importance','/alerts'])
def test_analytics(client,auth,path):
    r=client.get('/api'+path,headers=auth);assert r.status_code==200,r.text

@pytest.mark.parametrize('kind,format',[('providers','csv'),('providers','pdf'),('claims','csv'),('claims','pdf')])
def test_exports(client,auth,kind,format):
    r=client.get(f'/api/reports/{kind}?format={format}',headers=auth)
    assert r.status_code==200,r.text
    assert len(r.content)>50
    if format=='pdf': assert r.content.startswith(b'%PDF')

def test_validation_and_permissions(client,auth):
    assert client.get('/api/providers?page_size=1000',headers=auth).status_code==422
    assert client.get('/api/claims/missing',headers=auth).status_code==404
    assert client.post('/api/predict/batch',json={'claim_ids':[]},headers=auth).status_code==422
    assert client.post('/api/auth/register',json={'username':'someone','password':'long-enough-password'},headers=auth).status_code==403
    assert client.patch('/api/alerts/1',json={'status':'reviewed'},headers=auth).status_code==403
    assert client.post('/api/auth/login',json={'username':'nonexistent','password':'incorrect-password'}).status_code==401


def test_valid_batch_and_invalid_token(client,auth):
    cid=client.get('/api/claims?page_size=1',headers=auth).json()['items'][0]['id']
    r=client.post('/api/predict/batch',headers=auth,json={'claim_ids':[cid]})
    assert r.status_code==200,r.text
    assert r.json()[0]['claim_id']==cid
    assert client.get('/api/auth/me',headers={'Authorization':'Bearer invalid'}).status_code==401
    assert client.get('/api/analytics/distributions',headers=auth).status_code==200


def test_fresh_migrations(client):
    import os,sys,subprocess
    from sqlalchemy import text
    from sqlalchemy.engine import make_url
    from backend.app.db import engine,settings
    schema='migration_test_'+uuid.uuid4().hex[:10]
    with engine.begin() as c:c.execute(text(f'CREATE SCHEMA {schema}'))
    try:
        url=make_url(settings.database_url)
        query=dict(url.query);query['options']='-csearch_path='+schema
        env=dict(os.environ,DATABASE_URL=url.set(query=query).render_as_string(hide_password=False))
        r=subprocess.run([sys.executable,'-m','alembic','upgrade','head'],env=env,capture_output=True,text=True)
        assert r.returncode==0,r.stderr
        with engine.connect() as c:
            n=c.scalar(text('SELECT count(*) FROM information_schema.tables WHERE table_schema=:schema'),{'schema':schema})
            assert n==12  # eleven app tables plus Alembic version
    finally:
        with engine.begin() as c:c.execute(text(f'DROP SCHEMA {schema} CASCADE'))
