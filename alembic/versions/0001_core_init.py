"""
core_init minimal tables + RLS

Revision ID: 0001_core_init
Revises:
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0001_core_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # UUID generator
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

    # -----------------------
    # TENANTS (NO RLS)
    # -----------------------
    op.create_table(
        "tenants",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )

    # -----------------------
    # USERS (RLS)
    # -----------------------
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_unique_constraint("uq_users_tenant_email", "users", ["tenant_id", "email"])

    # -----------------------
    # PATIENTS (RLS)
    # -----------------------
    op.create_table(
        "patients",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_patients_tenant_id", "patients", ["tenant_id"])

    # -----------------------
    # CASES (RLS)
    # -----------------------
    op.create_table(
        "cases",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_cases_tenant_id", "cases", ["tenant_id"])

    # -----------------------
    # RLS POLICIES
    # -----------------------
    tenant_tables = ["users", "patients", "cases"]
    for tbl in tenant_tables:
        op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY;")
        op.execute(f"""
            CREATE POLICY tenant_isolation_{tbl}
            ON {tbl}
            USING (
                tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            )
            WITH CHECK (
                tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            );
        """)


def downgrade():
    for tbl in ["users", "patients", "cases"]:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{tbl} ON {tbl};")
        op.execute(f"ALTER TABLE {tbl} DISABLE ROW LEVEL SECURITY;")

    op.drop_table("cases")
    op.drop_table("patients")
    op.drop_table("users")
    op.drop_table("tenants")