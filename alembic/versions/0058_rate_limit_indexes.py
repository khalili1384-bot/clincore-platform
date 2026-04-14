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


def downgrade() -> None:
    op.execute("ALTER TABLE usage_events ENABLE ROW LEVEL SECURITY")
    
    # Drop index first
    op.drop_index('idx_usage_events_tenant_date', table_name='usage_events')
    
    # Drop table
    op.drop_table('usage_events')
