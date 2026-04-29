"""rate limit indexes

Revision ID: 0058
Revises: 0057
Create Date: 2026-04-13 09:08:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0058'
down_revision = '0057'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create usage_events table
    op.create_table(
        'usage_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', sa.Text(), nullable=False),
        sa.Column('endpoint_path', sa.Text(), nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    
    # Create index on tenant_id and created_at for efficient rate limiting queries
    op.create_index(
        'idx_usage_events_tenant_date',
        'usage_events',
        ['tenant_id', 'created_at']
    )
    
    # Disable RLS on usage_events (infrastructure table, not user data)
    op.execute("ALTER TABLE usage_events DISABLE ROW LEVEL SECURITY")
    
    # Create rate_limit_counters table
    op.execute("""
        CREATE TABLE IF NOT EXISTS rate_limit_counters (
            id          BIGSERIAL PRIMARY KEY,
            tenant_id   UUID NOT NULL,
            endpoint    VARCHAR(120) NOT NULL,
            window_day  DATE NOT NULL,
            count       INTEGER NOT NULL DEFAULT 0,
            CONSTRAINT uq_rl_tenant_endpoint_day UNIQUE (tenant_id, endpoint, window_day)
        )
    """)
    
    # Create index for efficient lookups
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_rl_tenant_day
            ON rate_limit_counters (tenant_id, window_day)
    """)
    
    # Disable RLS on rate_limit_counters (infrastructure table)
    op.execute("ALTER TABLE rate_limit_counters DISABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    # Drop rate_limit_counters
    op.execute("DROP INDEX IF EXISTS idx_rl_tenant_day")
    op.execute("DROP TABLE IF EXISTS rate_limit_counters")
    
    # Drop usage_events
    op.execute("ALTER TABLE usage_events ENABLE ROW LEVEL SECURITY")
    op.drop_index('idx_usage_events_tenant_date', table_name='usage_events')
    op.drop_table('usage_events')
