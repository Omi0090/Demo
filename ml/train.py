"""Train on real prepared records. Select provider model by training CV AP only."""
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import shap
from sklearn.model_selection import train_test_split, StratifiedKFold, GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, average_precision_score, confusion_matrix
from xgboost import XGBClassifier
from ml.claim_detection.rules import fit_rule_reference, review_indicators
import hashlib
import importlib.metadata

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / 'ml/saved_models'
PREPARED = ROOT / 'reports/prepared'
CLAIM_FEATURES = ['InscClaimAmtReimbursed','DeductibleAmtPaid','claim_duration_days','diagnosis_count','procedure_count','patient_historical_claim_count','provider_historical_average','claim_to_provider_average_ratio','is_inpatient']


def claim_matrix(frame):
    out = frame.copy()
    out['is_inpatient'] = out.claim_type.eq('inpatient').astype(int)
    return out[CLAIM_FEATURES].apply(pd.to_numeric, errors='coerce').replace([np.inf,-np.inf],np.nan)


def train():
    MODELS.mkdir(parents=True, exist_ok=True)
    providers = pd.read_csv(PREPARED/'provider_features.csv.gz')
    features = [c for c in providers if c not in ['Provider','PotentialFraud']]
    X = providers[features].replace([np.inf,-np.inf],np.nan)
    y = providers.PotentialFraud.eq('Yes').astype(int)
    train_idx, test_idx = train_test_split(np.arange(len(y)),test_size=.2,stratify=y,random_state=42)
    cv = StratifiedKFold(3, shuffle=True, random_state=42)
    ratio = float((y.iloc[train_idx]==0).sum()/(y.iloc[train_idx]==1).sum())
    candidates = {
        'Logistic Regression': (LogisticRegression(class_weight='balanced',max_iter=2000,random_state=42), {'model__C':[.1,1]}),
        'Decision Tree': (DecisionTreeClassifier(class_weight='balanced',random_state=42),{'model__max_depth':[4,8],'model__min_samples_leaf':[5]}),
        'Random Forest': (RandomForestClassifier(n_estimators=160,class_weight='balanced',n_jobs=2,random_state=42),{'model__max_depth':[8,None],'model__min_samples_leaf':[2]}),
        'XGBoost': (XGBClassifier(n_estimators=180,learning_rate=.06,scale_pos_weight=ratio,eval_metric='logloss',n_jobs=2,random_state=42),{'model__max_depth':[3,5]}),
    }
    results=[]; fitted={}
    for name,(model,grid) in candidates.items():
        pipe=Pipeline([('imputer',SimpleImputer(strategy='median',keep_empty_features=True)),('scale',StandardScaler()),('model',model)])
        search=GridSearchCV(pipe,grid,scoring='average_precision',cv=cv,n_jobs=1,error_score='raise')
        search.fit(X.iloc[train_idx],y.iloc[train_idx])
        fitted[name]=search.best_estimator_
        p=search.predict_proba(X.iloc[test_idx])[:,1]; pred=p>=.5; truth=y.iloc[test_idx]
        results.append(dict(model=name,cv_pr_auc=float(search.best_score_),accuracy=accuracy_score(truth,pred),precision=precision_score(truth,pred,zero_division=0),recall=recall_score(truth,pred),f1=f1_score(truth,pred),roc_auc=roc_auc_score(truth,p),pr_auc=average_precision_score(truth,p),confusion_matrix=confusion_matrix(truth,pred).tolist(),parameters=search.best_params_))
        print(name,results[-1],flush=True)
    best=max(results,key=lambda r:r['cv_pr_auc'])['model']
    pipe=fitted[best]
    all_p=pipe.predict_proba(X)[:,1]
    pre=pipe[:-1]; z=pre.transform(X)
    background=pre.transform(X.iloc[train_idx].sample(min(100,len(train_idx)),random_state=42))
    model=pipe.named_steps['model']
    if best=='Logistic Regression':
        explainer=shap.LinearExplainer(model,background)
        values=explainer.shap_values(z); base=float(explainer.expected_value); units='log_odds'
    else:
        explainer=shap.TreeExplainer(model)
        values=explainer.shap_values(z)
        if isinstance(values,list): values=values[1]
        if values.ndim==3: values=values[:,:,1]
        expected=np.asarray(explainer.expected_value).ravel()
        base=float(expected[-1]); units='probability' if best in ['Random Forest','Decision Tree'] else 'log_odds'
    reconstructed=values.sum(axis=1)+base
    predicted=1/(1+np.exp(-reconstructed)) if units=='log_odds' else reconstructed
    max_error=float(np.max(np.abs(predicted-all_p)))
    if max_error>1e-4: raise ValueError(f'SHAP additivity failed: {max_error}')
    metadata={'best_model':best,'selection':'maximum training-fold average precision; holdout not used for selection','seed':42,'threshold':.5,'train_providers':len(train_idx),'test_providers':len(test_idx),'metrics':results,'features':features,'shap_units':units,'shap_base':base,'shap_max_additivity_error':max_error,'probability_note':'Uncalibrated provider model probability, not verified fraud likelihood.'}
    joblib.dump({'pipeline':pipe,'features':features,'metadata':metadata},MODELS/'provider.joblib')
    pd.DataFrame({'Provider':providers.Provider,'probability':all_p,'split':np.where(np.isin(np.arange(len(y)),test_idx),'holdout','training')}).to_csv(MODELS/'provider_predictions.csv',index=False)
    np.savez_compressed(MODELS/'shap.npz',values=values)
    metadata['source_sha256'] = {p.name: hashlib.file_digest(p.open('rb'),'sha256').hexdigest() for p in (ROOT/'ml/data').glob('*.csv')}
    metadata['dependencies'] = {name:importlib.metadata.version(name) for name in ['pandas','numpy','scikit-learn','xgboost','shap','joblib']}
    (MODELS/'metrics.json').write_text(json.dumps(metadata,indent=2))
    joblib.dump({'pipeline':pipe,'features':features,'metadata':metadata},MODELS/'provider.joblib')
    train_providers=set(providers.iloc[train_idx].Provider)
    claims=pd.read_csv(PREPARED/'claims_prepared.csv.gz',dtype='string')
    claims['InscClaimAmtReimbursed']=pd.to_numeric(claims.InscClaimAmtReimbursed)
    matrix=claim_matrix(claims)
    eligible=claims.Provider.isin(train_providers)
    fit_index=claims.loc[eligible].sample(min(40000,int(eligible.sum())),random_state=42).index
    preprocessing=Pipeline([('imputer',SimpleImputer(strategy='median',keep_empty_features=True)),('scale',StandardScaler())])
    fit=preprocessing.fit_transform(matrix.loc[fit_index])
    iso=IsolationForest(n_estimators=120,contamination=.05,n_jobs=2,random_state=42).fit(fit)
    lof=LocalOutlierFactor(n_neighbors=25,novelty=True,contamination=.05,n_jobs=2).fit(fit)
    # Fixed fit-reference threshold: model scores are not probabilities.
    bundle={'preprocessing':preprocessing,'isolation':iso,'lof':lof,'features':CLAIM_FEATURES,
        'isolation_threshold':float(-iso.offset_),'lof_threshold':float(-lof.offset_),
        'high_amount':float(claims.loc[fit_index,'InscClaimAmtReimbursed'].quantile(.99)),
        'fit_claims':len(fit_index),'note':'Training-provider sample; retrospective chronological features; no verified claim fraud labels.'}
    bundle.update(fit_rule_reference(claims.loc[fit_index]))
    all_indicators=review_indicators(claims,bundle)
    joblib.dump(bundle,MODELS/'claim.joblib')
    outputs=[]
    for start in range(0,len(claims),10000):
        chunk=matrix.iloc[start:start+10000]; transformed=preprocessing.transform(chunk)
        si=-iso.score_samples(transformed); sl=-lof.score_samples(transformed)
        indicators=all_indicators[start:start+10000]
        outputs.extend({'ClaimID':cid,'isolation_score':float(a),'lof_score':float(b),'anomalous':bool(a>bundle['isolation_threshold'] or b>bundle['lof_threshold'] or rules),'indicators':json.dumps(rules)} for cid,a,b,rules in zip(claims.ClaimID.iloc[start:start+10000],si,sl,indicators))
        if start%100000==0: print('Scored claims',start,flush=True)
    pd.DataFrame(outputs).to_csv(MODELS/'claim_predictions.csv.gz',index=False,compression='gzip')
    print('Saved provider, SHAP and claim artifacts',flush=True)

if __name__=='__main__': train()
