"""
v036_billing_skeleton

Revision ID: a96162dee369
Revises: 0e397e47435e
Create Date: 2026-02-25 18:53:11.998178

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a96162dee369'
down_revision = '0e397e47435e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS api_keys (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            key_hash TEXT NOT NULL UNIQUE,
            label TEXT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_used_at TIMESTAMPTZ NULL
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_api_keys_tenant ON api_keys(tenant_id)"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'cases' AND column_name = 'billing_status'
            ) THEN
                ALTER TABLE cases
                    ADD COLUMN billing_status TEXT NOT NULL DEFAULT 'free';
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
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_cases_billing_status_allowed'
            ) THEN
                ALTER TABLE cases
                    ADD CONSTRAINT ck_cases_billing_status_allowed
                    CHECK (billing_status IN ('free', 'paid', 'subscription'));
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
                WHERE table_name = 'cases' AND column_name = 'api_client_id'
            ) THEN
                ALTER TABLE cases
                    ADD COLUMN api_client_id TEXT NULL;
            END IF;
        END;
        $$
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE cases DROP CONSTRAINT IF EXISTS ck_cases_billing_status_allowed"
    )
    op.execute("ALTER TABLE cases DROP COLUMN IF EXISTS api_client_id")
    op.execute("ALTER TABLE cases DROP COLUMN IF EXISTS billing_status")
    op.execute("DROP TABLE IF EXISTS api_keys CASCADE")
