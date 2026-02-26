"""
v035_access_logs

Revision ID: 0e397e47435e
Revises: 256690bbd45e
Create Date: 2026-02-25 18:26:49.045377

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0e397e47435e'
down_revision = '256690bbd45e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS access_logs (
            id BIGSERIAL PRIMARY KEY,
            tenant_id UUID NOT NULL,
            user_id UUID NOT NULL,
            case_id UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
            action VARCHAR(20) NOT NULL DEFAULT 'VIEW',
            accessed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_access_logs_case ON access_logs(case_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_access_logs_tenant ON access_logs(tenant_id)"
    )
    op.execute("ALTER TABLE access_logs ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies
                WHERE tablename = 'access_logs'
                  AND policyname = 'tenant_isolation_access_logs'
            ) THEN
                CREATE POLICY tenant_isolation_access_logs
                ON access_logs
                USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);
            END IF;
        END;
        $$
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS access_logs CASCADE")
