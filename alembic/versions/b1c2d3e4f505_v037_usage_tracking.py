"""
v037_usage_tracking

Revision ID: b1c2d3e4f505
Revises: a96162dee369
Create Date: 2026-02-25 19:00:00.000000
"""

from alembic import op


revision = 'b1c2d3e4f505'
down_revision = 'a96162dee369'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS usage_events (
            id BIGSERIAL PRIMARY KEY,
            tenant_id UUID NOT NULL,
            api_key_id UUID NOT NULL,
            endpoint TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_usage_tenant ON usage_events(tenant_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_usage_api_key ON usage_events(api_key_id)"
    )
    op.execute("ALTER TABLE usage_events ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies
                WHERE tablename = 'usage_events' AND policyname = 'usage_events_tenant_isolation'
            ) THEN
                CREATE POLICY usage_events_tenant_isolation ON usage_events
                    USING (tenant_id = current_setting('app.tenant_id')::uuid);
            END IF;
        END;
        $$
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'api_keys' AND column_name = 'revoked_at'
            ) THEN
                ALTER TABLE api_keys ADD COLUMN revoked_at TIMESTAMPTZ NULL;
            END IF;
        END;
        $$
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'api_keys' AND column_name = 'role'
            ) THEN
                ALTER TABLE api_keys ADD COLUMN role TEXT NOT NULL DEFAULT 'user';
            END IF;
        END;
        $$
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS usage_events CASCADE")
    op.execute("ALTER TABLE api_keys DROP COLUMN IF EXISTS revoked_at")
    op.execute("ALTER TABLE api_keys DROP COLUMN IF EXISTS role")
