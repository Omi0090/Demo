"""Explicit public schemas for independent provider risk and claim anomalies."""
from pydantic import BaseModel,Field
from typing import Literal
class Contribution(BaseModel):
    feature:str
    contribution:float
    value:float|int|None=None
class Explanation(BaseModel):
    base:float
    units:Literal['probability','log_odds']
    contributions:list[Contribution]
class ProviderRisk(BaseModel):
    probability:float=Field(ge=0,le=1)
    classification:Literal['Potentially Fraudulent','Non-Fraudulent']
    model_version:str
    split:str
    explanation:Explanation
    note:str
class ProviderRecord(BaseModel):
    id:str
    observed_label:Literal['Yes','No']
    features:dict[str,float|int|None]
    risk:ProviderRisk|None
class HybridResponse(BaseModel):
    claim_id:str
    result:Literal['Normal','Anomalous']
    isolation_score:float
    lof_score:float
    indicators:list[str]
    provider:ProviderRisk|None
    note:str
class ProviderInference(ProviderRecord):
    recomputed_probability:float=Field(ge=0,le=1)
class DashboardSummary(BaseModel):
    providers:int
    patients:int
    claims:int
    labeled_potential_fraud:int
    high_risk_providers:int
    anomalous_claims:int
    reimbursement:float
    alerts:int
