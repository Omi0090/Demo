"""Small synthetic fixtures for algorithm plumbing; actual artifacts checked separately."""
import numpy as np
import pandas as pd
import pytest
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier,IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from xgboost import XGBClassifier
from ml.claim_detection.rules import fit_rule_reference,review_indicators

@pytest.mark.parametrize('estimator',[LogisticRegression(),DecisionTreeClassifier(max_depth=2),RandomForestClassifier(n_estimators=10,random_state=1),XGBClassifier(n_estimators=10,n_jobs=1)])
def test_training_and_joblib_roundtrip(estimator,tmp_path):
    import joblib
    rng=np.random.default_rng(7);x=rng.normal(size=(100,4));y=(x[:,0]+x[:,1]>0).astype(int);x[0,0]=np.nan
    pipe=make_pipeline(SimpleImputer(),StandardScaler(),estimator).fit(x,y)
    joblib.dump(pipe,tmp_path/'test.joblib');p=joblib.load(tmp_path/'test.joblib').predict_proba(x)
    assert p.shape==(100,2) and np.isfinite(p).all()

def test_anomaly_algorithms_score_extreme_record():
    rng=np.random.default_rng(12);x=rng.normal(0,.2,size=(200,3))
    normal=np.zeros((1,3));extreme=np.ones((1,3))*100
    for m in [IsolationForest(random_state=42),LocalOutlierFactor(novelty=True)]:
        m.fit(x)
        assert m.score_samples(extreme)[0]<m.score_samples(normal)[0]

def test_rules_normal_repeated_and_rare():
    frame=pd.DataFrame({'Provider':['P1']*3,'BeneID':['B1','B1','B2'],
        'ClaimStartDt':['2009-01-01']*3,'ClaimEndDt':['2009-01-01']*3,
        'claim_type':['outpatient']*3,'InscClaimAmtReimbursed':[100,100,100000],
        'claim_to_provider_average_ratio':[1,1,1000], 'patient_historical_claim_count':[1,1,60],
        'ClmDiagnosisCode_1':['001','001','999'],'ClmProcedureCode_1':['01','01','99']})
    reference=fit_rule_reference(frame.iloc[:2]);reference['high_amount']=1000
    result=review_indicators(frame,reference)
    assert any('Repeated billing' in x for x in result[0])
    assert any('Rare diagnosis' in x for x in result[2])
    assert any('99th' in x for x in result[2])
    single=frame.iloc[[0]].copy();single['BeneID']='B3'
    assert review_indicators(single,reference)==[[]]

def test_tree_shap_additivity():
    import shap
    rng=np.random.default_rng(3);x=rng.normal(size=(50,3));y=(x[:,0]>0).astype(int)
    model=XGBClassifier(n_estimators=10,n_jobs=1).fit(x,y)
    explanation=shap.TreeExplainer(model)(x)
    reconstructed=1/(1+np.exp(-(explanation.values.sum(axis=1)+explanation.base_values)))
    assert np.allclose(reconstructed,model.predict_proba(x)[:,1],atol=1e-5)
