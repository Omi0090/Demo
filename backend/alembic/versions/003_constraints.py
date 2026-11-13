"""Domain constraints; also supports a fresh schema created with current metadata."""
from alembic import op
from sqlalchemy import inspect
revision='003'
down_revision='002'
branch_labels=None
depends_on=None
RULES=[('users','ck_user_role',"role IN ('admin','analyst')"),('providers','ck_provider_label',"observed_label IN ('Yes','No')"),('claims','ck_claim_type',"claim_type IN ('inpatient','outpatient')"),('provider_predictions','ck_probability','probability >= 0 AND probability <= 1'),('fraud_alerts','ck_alert_status',"status IN ('open','reviewed','dismissed')")]
def upgrade():
    for table,name,expression in RULES:
        if name not in {c['name'] for c in inspect(op.get_bind()).get_check_constraints(table)}:
            op.create_check_constraint(name,table,expression)
def downgrade():
    for table,name,_ in RULES: op.drop_constraint(name,table,type_='check')
