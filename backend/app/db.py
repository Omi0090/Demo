from datetime import datetime, timezone
from sqlalchemy import create_engine, String, Float, Integer, DateTime, ForeignKey, JSON, Boolean, UniqueConstraint, Index, CheckConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = 'postgresql+psycopg://localhost/healthcare_fraud'
    jwt_secret: str
    jwt_expire_minutes: int = 60
    frontend_origin: str = 'http://localhost:5173'
    model_config = SettingsConfigDict(env_file='.env',extra='ignore')

settings=Settings()
if len(settings.jwt_secret)<32 or settings.jwt_secret.startswith('REPLACE_'):
    raise ValueError('Set JWT_SECRET to a random secret of at least 32 characters')
engine=create_engine(settings.database_url, pool_pre_ping=True)
Session=sessionmaker(engine)
class Base(DeclarativeBase): pass
class Timed:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=lambda: datetime.now(timezone.utc))
class User(Timed,Base):
    __tablename__='users'
    __table_args__=(CheckConstraint("role IN ('admin','analyst')",name='ck_user_role'),)
    id: Mapped[int]=mapped_column(primary_key=True)
    username: Mapped[str]=mapped_column(String(80),unique=True)
    password_hash: Mapped[str]=mapped_column(String(255))
    role: Mapped[str]=mapped_column(String(20),default='analyst')
class Patient(Timed,Base):
    __tablename__='patients'
    id: Mapped[str]=mapped_column(String(40),primary_key=True)
    attributes: Mapped[dict]=mapped_column(JSON)
class Provider(Timed,Base):
    __tablename__='providers'
    __table_args__=(CheckConstraint("observed_label IN ('Yes','No')",name='ck_provider_label'),)
    id: Mapped[str]=mapped_column(String(40),primary_key=True)
    observed_label: Mapped[str]=mapped_column(String(3))
    features: Mapped[dict]=mapped_column(JSON)
class Claim(Timed,Base):
    __tablename__='claims'
    __table_args__=(CheckConstraint("claim_type IN ('inpatient','outpatient')",name='ck_claim_type'),)
    id: Mapped[str]=mapped_column(String(40),primary_key=True)
    provider_id: Mapped[str]=mapped_column(ForeignKey('providers.id'),index=True)
    patient_id: Mapped[str]=mapped_column(ForeignKey('patients.id'),index=True)
    claim_type: Mapped[str]=mapped_column(String(20),index=True)
    start_date: Mapped[str]=mapped_column(String(10),index=True)
    end_date: Mapped[str]=mapped_column(String(10))
    amount: Mapped[float]=mapped_column(Float)
    deductible: Mapped[float|None]=mapped_column(Float,nullable=True)
    attending: Mapped[str|None]=mapped_column(String(40),nullable=True,index=True)
    operating: Mapped[str|None]=mapped_column(String(40),nullable=True,index=True)
    other: Mapped[str|None]=mapped_column(String(40),nullable=True,index=True)
    features: Mapped[dict]=mapped_column(JSON)
class Diagnosis(Base):
    __tablename__='claim_diagnoses'
    id: Mapped[int]=mapped_column(primary_key=True)
    claim_id: Mapped[str]=mapped_column(ForeignKey('claims.id'),index=True)
    position: Mapped[int]=mapped_column(Integer)
    code: Mapped[str]=mapped_column(String(40),index=True)
    __table_args__=(UniqueConstraint('claim_id','position'),)
class Procedure(Base):
    __tablename__='claim_procedures'
    id: Mapped[int]=mapped_column(primary_key=True)
    claim_id: Mapped[str]=mapped_column(ForeignKey('claims.id'),index=True)
    position: Mapped[int]=mapped_column(Integer)
    code: Mapped[str]=mapped_column(String(40),index=True)
    __table_args__=(UniqueConstraint('claim_id','position'),)
class ProviderPrediction(Timed,Base):
    __tablename__='provider_predictions'
    __table_args__=(CheckConstraint("probability >= 0 AND probability <= 1",name='ck_probability'),)
    provider_id: Mapped[str]=mapped_column(ForeignKey('providers.id'),primary_key=True)
    probability: Mapped[float]=mapped_column(Float,index=True)
    model_version: Mapped[str]=mapped_column(String(40))
    split: Mapped[str]=mapped_column(String(20))
    explanation: Mapped[dict]=mapped_column(JSON)
class ClaimAnomaly(Timed,Base):
    __tablename__='claim_anomalies'
    claim_id: Mapped[str]=mapped_column(ForeignKey('claims.id'),primary_key=True)
    isolation_score: Mapped[float]=mapped_column(Float)
    lof_score: Mapped[float]=mapped_column(Float)
    anomalous: Mapped[bool]=mapped_column(Boolean,index=True)
    indicators: Mapped[list]=mapped_column(JSON)
    model_version: Mapped[str]=mapped_column(String(40))
class Alert(Timed,Base):
    __tablename__='fraud_alerts'
    __table_args__=(CheckConstraint("status IN ('open','reviewed','dismissed')",name='ck_alert_status'),)
    id: Mapped[int]=mapped_column(primary_key=True)
    claim_id: Mapped[str]=mapped_column(ForeignKey('claims.id'),index=True)
    reason: Mapped[str]=mapped_column(String(1024))
    status: Mapped[str]=mapped_column(String(20),default='open')
class Metric(Timed,Base):
    __tablename__='model_metrics'
    id: Mapped[int]=mapped_column(primary_key=True)
    model_name: Mapped[str]=mapped_column(String(80),unique=True)
    payload: Mapped[dict]=mapped_column(JSON)
class Audit(Timed,Base):
    __tablename__='audit_logs'
    id: Mapped[int]=mapped_column(primary_key=True)
    actor_id: Mapped[int|None]=mapped_column(ForeignKey('users.id'),nullable=True)
    action: Mapped[str]=mapped_column(String(80))
    entity: Mapped[str]=mapped_column(String(80))
