"""Explicit review rules. No indicator is a verified claim fraud label."""
import numpy as np
import pandas as pd


def fit_rule_reference(claims):
    """Call only on training-provider fit records."""
    pair=claims['ClmDiagnosisCode_1'].fillna('')+'|'+claims['ClmProcedureCode_1'].fillna('')
    available=claims['ClmDiagnosisCode_1'].notna() & claims['ClmProcedureCode_1'].notna()
    amounts=pd.to_numeric(claims.InscClaimAmtReimbursed,errors='coerce')
    median=float(amounts.median()); mad=float((amounts-median).abs().median())
    return {'pair_counts':pair[available].value_counts().to_dict(),'amount_median':median,'amount_mad':mad}


def review_indicators(claims,reference):
    """Duplicate/repetition indicators are retrospective, including same-day patterns."""
    amount=pd.to_numeric(claims.InscClaimAmtReimbursed,errors='coerce')
    ratio=pd.to_numeric(claims.claim_to_provider_average_ratio,errors='coerce')
    count=pd.to_numeric(claims.patient_historical_claim_count,errors='coerce')
    keys=['Provider','BeneID','ClaimStartDt','ClaimEndDt','claim_type','InscClaimAmtReimbursed']
    keys += [c for c in claims if c.startswith(('ClmDiagnosisCode_','ClmProcedureCode_'))]
    duplicate=claims.duplicated(keys,keep=False)
    procedure=claims.ClmProcedureCode_1
    repeated=procedure.notna() & claims.duplicated(['Provider','BeneID','ClaimStartDt','ClmProcedureCode_1'],keep=False)
    pairs=claims.ClmDiagnosisCode_1.fillna('')+'|'+procedure.fillna('')
    rare=claims.ClmDiagnosisCode_1.notna() & procedure.notna() & pairs.map(reference['pair_counts']).fillna(0).le(1)
    # Heavy-tailed amounts require a conservative threshold; descriptive review only.
    robust=(amount-reference['amount_median']).abs()/(1.4826*max(reference['amount_mad'],1.0))
    flags=[(amount>reference['high_amount'],'Above training 99th-percentile amount'),
           (ratio>5,'Amount exceeds 5x prior provider mean'),
           (count>50,'More than 50 prior patient claims'),
           (duplicate,'Repeated billing signature (retrospective review)'),
           (repeated,'Repeated patient procedure on same date'),
           (rare,'Rare diagnosis/procedure pair in training reference'),
           (robust>50,'Extreme robust amount deviation (training median/MAD)')]
    output=[[] for _ in range(len(claims))]
    for mask,message in flags:
        for i in np.flatnonzero(mask.fillna(False).to_numpy()): output[i].append(message)
    return output
