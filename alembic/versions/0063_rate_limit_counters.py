"""Rate limit counters table

Revision ID: 0063
Revises: 0062
Create Date: 2026-05-03 10:44:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0063'
down_revision = '0062'
branch_labels = None
depends_on = None


def upgrade():
    # Create rate_limit_counters table
    op.execute("""
        CREATE TABLE rate_limit_counters (
            id          SERIAL PRIMARY KEY,
            tenant_id   UUID NOT NULL,
            endpoint    VARCHAR(255) NOT NULL,
            window_date DATE NOT NULL,
            count       INTEGER NOT NULL DEFAULT 0,
            CONSTRAINT uq_rl_tenant_endpoint_date UNIQUE (tenant_id, endpoint, window_date)
        )
    """)
    
    # Create index
    op.execute("""
        CREATE INDEX idx_rl_tenant_endpoint_date
            ON rate_limit_counters (tenant_id, endpoint, window_date)
    """)


def downgrade():
    op.drop_table("rate_limit_counters")
