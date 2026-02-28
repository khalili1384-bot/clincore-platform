"""
v046_mcare_feedback_loop

Revision ID: d046a1b2c3e4
Revises: c045d6e7f809
Create Date: 2026-02-27 21:30:00.000000
"""

from alembic import op


revision = 'd046a1b2c3e4'
down_revision = 'c045d6e7f809'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS mcare_feedback (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            user_id UUID NULL,
            case_id UUID NULL,
            request_id TEXT NULL,
            locale TEXT NULL,
            narrative_hash TEXT NULL,
            predicted_top1 TEXT NOT NULL,
            predicted_top3 JSONB NOT NULL,
            chosen_remedy TEXT NOT NULL,
            outcome_type TEXT NOT NULL,
            outcome_score INT NULL,
            notes TEXT NULL,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_predicted_top3_is_array CHECK (jsonb_typeof(predicted_top3) = 'array'),
            CONSTRAINT chk_outcome_score_range CHECK (outcome_score IS NULL OR (outcome_score BETWEEN 1 AND 10)),
            CONSTRAINT chk_nonempty_predicted_top1 CHECK (length(predicted_top1) > 0),
            CONSTRAINT chk_nonempty_chosen_remedy CHECK (length(chosen_remedy) > 0)
        )
        """
    )

    # Indexes
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_mcare_feedback_tenant_time "
        "ON mcare_feedback(tenant_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_mcare_feedback_tenant_top1 "
        "ON mcare_feedback(tenant_id, predicted_top1)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_mcare_feedback_tenant_chosen "
        "ON mcare_feedback(tenant_id, chosen_remedy)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_mcare_feedback_tenant_case "
        "ON mcare_feedback(tenant_id, case_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_mcare_feedback_metadata_gin "
        "ON mcare_feedback USING GIN (metadata)"
    )

    # Enable RLS
    op.execute("ALTER TABLE mcare_feedback ENABLE ROW LEVEL SECURITY")

    # SELECT/INSERT policy: tenant isolation
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies
                WHERE tablename = 'mcare_feedback'
                  AND policyname = 'mcare_feedback_tenant_select_insert'
            ) THEN
                CREATE POLICY mcare_feedback_tenant_select_insert ON mcare_feedback
                    FOR ALL
                    USING (tenant_id = current_setting('app.tenant_id')::uuid)
                    WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
            END IF;
        END;
        $$
        """
    )

    # UPDATE policy: deny (append-only)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies
                WHERE tablename = 'mcare_feedback'
                  AND policyname = 'mcare_feedback_no_update'
            ) THEN
                CREATE POLICY mcare_feedback_no_update ON mcare_feedback
                    FOR UPDATE
                    USING (false);
            END IF;
        END;
        $$
        """
    )

    # DELETE policy: deny (append-only)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies
                WHERE tablename = 'mcare_feedback'
                  AND policyname = 'mcare_feedback_no_delete'
            ) THEN
                CREATE POLICY mcare_feedback_no_delete ON mcare_feedback
                    FOR DELETE
                    USING (false);
            END IF;
        END;
        $$
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS mcare_feedback CASCADE")
