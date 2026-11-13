"""Allow multiple transparent rule explanations without truncation."""
from alembic import op
import sqlalchemy as sa
revision='002'
down_revision='001'
branch_labels=None
depends_on=None

def upgrade():
    op.alter_column('fraud_alerts','reason',type_=sa.String(1024),existing_type=sa.String(255))
def downgrade():
    op.alter_column('fraud_alerts','reason',type_=sa.String(255),existing_type=sa.String(1024))
