"""
case_engine_core_v032

Revision ID: 34bf50c7d602
Revises: 20f4b88b6b43
Create Date: 2026-02-24 22:54:47.031355

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '34bf50c7d602'
down_revision = '20f4b88b6b43'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

    op.create_table(
        "engine_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("version", sa.String(length=50), nullable=False, unique=True),
        sa.Column("git_commit_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
    )

    op.create_table(
        "datasets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("hash_sha256", sa.CHAR(length=64), nullable=False, unique=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
    )

    op.create_table(
        "patient_consents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consent_type", sa.String(length=50), nullable=False),
        sa.Column("granted_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("expiry_date", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("is_revoked", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
    )

    op.create_table(
        "case_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("remedy_name", sa.String(length=100), nullable=False),
        sa.Column("raw_score", sa.Float(), nullable=False),
        sa.Column("mcare_score", sa.Float(), nullable=True),
        sa.Column("coverage", sa.Float(), nullable=True),
        sa.Column("mind_strong_hits", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("idx_case_results_case_rank", "case_results", ["case_id", "rank"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("table_name", sa.String(length=50), nullable=False),
        sa.Column("record_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("idx_audit_logs_tenant_time", "audit_logs", ["tenant_id", "created_at"])

    op.create_table(
        "case_outcomes",
        sa.Column("case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cases.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("outcome_type", sa.String(length=30), nullable=True),
        sa.Column("recorded_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("recorded_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
    )

    op.add_column("cases", sa.Column("input_payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.add_column("cases", sa.Column("engine_version_id", sa.Integer(), nullable=True))
    op.add_column("cases", sa.Column("dataset_id", sa.Integer(), nullable=True))
    op.add_column("cases", sa.Column("params_hash_sha256", sa.CHAR(length=64), nullable=True))
    op.add_column("cases", sa.Column("random_seed", sa.String(length=64), nullable=True))
    op.add_column("cases", sa.Column("ranking_snapshot", postgresql.JSONB(), nullable=True))
    op.add_column("cases", sa.Column("result_signature", sa.String(length=64), nullable=True))
    op.add_column("cases", sa.Column("replay_verified_at", sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column("cases", sa.Column("consent_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("cases", sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'draft'")))
    op.add_column("cases", sa.Column("finalized_at", sa.TIMESTAMP(timezone=True), nullable=True))

    op.create_foreign_key(
        "fk_cases_engine_version_id_engine_versions",
        "cases",
        "engine_versions",
        ["engine_version_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_cases_dataset_id_datasets",
        "cases",
        "datasets",
        ["dataset_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_cases_consent_id_patient_consents",
        "cases",
        "patient_consents",
        ["consent_id"],
        ["id"],
    )

    op.create_check_constraint(
        "ck_cases_status_allowed",
        "cases",
        "status IN ('draft','finalized','archived')",
    )

    op.create_index(
        "idx_cases_tenant_status_created",
        "cases",
        ["tenant_id", "status", "created_at"],
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION enforce_case_immutability()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'Delete is not allowed on cases';
            END IF;

            IF OLD.status = 'finalized' THEN
                RAISE EXCEPTION 'Finalized cases are immutable';
            END IF;

            RETURN NEW;
        END;
        $$;
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_enforce_case_immutability
        BEFORE UPDATE OR DELETE ON cases
        FOR EACH ROW
        EXECUTE FUNCTION enforce_case_immutability();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_audit_modification()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs is WORM and cannot be updated or deleted';
        END;
        $$;
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_prevent_audit_modification
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW
        EXECUTE FUNCTION prevent_audit_modification();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_audit_modification ON audit_logs;")
    op.execute("DROP TRIGGER IF EXISTS trg_enforce_case_immutability ON cases;")

    op.execute("DROP FUNCTION IF EXISTS prevent_audit_modification();")
    op.execute("DROP FUNCTION IF EXISTS enforce_case_immutability();")

    op.drop_index("idx_cases_tenant_status_created", table_name="cases")

    op.drop_constraint("ck_cases_status_allowed", "cases", type_="check")
    op.drop_constraint("fk_cases_consent_id_patient_consents", "cases", type_="foreignkey")
    op.drop_constraint("fk_cases_dataset_id_datasets", "cases", type_="foreignkey")
    op.drop_constraint("fk_cases_engine_version_id_engine_versions", "cases", type_="foreignkey")

    op.drop_column("cases", "finalized_at")
    op.drop_column("cases", "status")
    op.drop_column("cases", "consent_id")
    op.drop_column("cases", "replay_verified_at")
    op.drop_column("cases", "result_signature")
    op.drop_column("cases", "ranking_snapshot")
    op.drop_column("cases", "random_seed")
    op.drop_column("cases", "params_hash_sha256")
    op.drop_column("cases", "dataset_id")
    op.drop_column("cases", "engine_version_id")
    op.drop_column("cases", "input_payload")

    op.drop_table("case_outcomes")

    op.drop_index("idx_audit_logs_tenant_time", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("idx_case_results_case_rank", table_name="case_results")
    op.drop_table("case_results")

    op.drop_table("patient_consents")
    op.drop_table("datasets")
    op.drop_table("engine_versions")
