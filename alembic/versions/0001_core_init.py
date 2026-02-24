"""fix rls nullif handling"""

from alembic import op

revision = "0001_core_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_users ON users")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_patients ON patients")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_cases ON cases")

    op.execute("""
        CREATE POLICY tenant_isolation_users
        ON users
        USING (
            tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        )
        WITH CHECK (
            tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        )
    """)

    op.execute("""
        CREATE POLICY tenant_isolation_patients
        ON patients
        USING (
            tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        )
        WITH CHECK (
            tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        )
    """)

    op.execute("""
        CREATE POLICY tenant_isolation_cases
        ON cases
        USING (
            tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        )
        WITH CHECK (
            tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        )
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_users ON users")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_patients ON patients")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_cases ON cases")

    op.execute("""
        CREATE POLICY tenant_isolation_users
        ON users
        USING (
            tenant_id = current_setting('app.tenant_id', true)::uuid
        )
        WITH CHECK (
            tenant_id = current_setting('app.tenant_id', true)::uuid
        )
    """)

    op.execute("""
        CREATE POLICY tenant_isolation_patients
        ON patients
        USING (
            tenant_id = current_setting('app.tenant_id', true)::uuid
        )
        WITH CHECK (
            tenant_id = current_setting('app.tenant_id', true)::uuid
        )
    """)

    op.execute("""
        CREATE POLICY tenant_isolation_cases
        ON cases
        USING (
            tenant_id = current_setting('app.tenant_id', true)::uuid
        )
        WITH CHECK (
            tenant_id = current_setting('app.tenant_id', true)::uuid
        )
    """)