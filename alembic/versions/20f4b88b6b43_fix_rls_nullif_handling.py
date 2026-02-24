"""
fix rls nullif handling + security grants

Revision ID: 20f4b88b6b43
Revises: 0001_core_init
Create Date: 2026-02-20 21:33:30.191469
"""

from alembic import op

revision = "20f4b88b6b43"
down_revision = "0001_core_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    DO $$
    BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'clincore_user') THEN
        EXECUTE 'ALTER ROLE clincore_user NOBYPASSRLS';
        EXECUTE 'ALTER ROLE clincore_user NOSUPERUSER';
      END IF;
    END $$;

    GRANT USAGE ON SCHEMA public TO clincore_user;

    -- tenants has NO RLS, tests need direct insert/select
    GRANT SELECT, INSERT ON TABLE tenants TO clincore_user;

    -- RLS tables: allow access, RLS will filter to 0 rows if no tenant context
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE users, patients, cases TO clincore_user;

    -- future-proof sequences (if you add identity/serial later)
    GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO clincore_user;

    ALTER DEFAULT PRIVILEGES IN SCHEMA public
      GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO clincore_user;

    ALTER DEFAULT PRIVILEGES IN SCHEMA public
      GRANT USAGE, SELECT ON SEQUENCES TO clincore_user;
    """)


def downgrade() -> None:
    op.execute("""
    REVOKE ALL ON TABLE cases FROM clincore_user;
    REVOKE ALL ON TABLE patients FROM clincore_user;
    REVOKE ALL ON TABLE users FROM clincore_user;
    REVOKE ALL ON TABLE tenants FROM clincore_user;
    REVOKE USAGE ON SCHEMA public FROM clincore_user;
    """)