"""
v034_replay_verification

Revision ID: 256690bbd45e
Revises: 9ab846c6a33b
Create Date: 2026-02-25 18:07:58.376331

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '256690bbd45e'
down_revision = '9ab846c6a33b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TABLE cases ADD COLUMN IF NOT EXISTS replay_verified_at TIMESTAMP WITH TIME ZONE"
    ))
    conn.execute(sa.text(
        "ALTER TABLE cases ADD COLUMN IF NOT EXISTS replay_verification_ok BOOLEAN"
    ))
    conn.execute(sa.text(
        "ALTER TABLE cases ADD COLUMN IF NOT EXISTS replay_verification_details JSONB"
    ))
    conn.execute(sa.text(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'chk_replay_only_on_finalized'
                  AND conrelid = 'cases'::regclass
            ) THEN
                ALTER TABLE cases ADD CONSTRAINT chk_replay_only_on_finalized
                CHECK (
                    (status != 'finalized' AND replay_verified_at IS NULL AND replay_verification_ok IS NULL)
                    OR (status = 'finalized')
                );
            END IF;
        END;
        $$
        """
    ))

    conn.execute(sa.text(
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
                IF (
                    NEW.replay_verified_at IS DISTINCT FROM OLD.replay_verified_at
                    OR NEW.replay_verification_ok IS DISTINCT FROM OLD.replay_verification_ok
                    OR NEW.replay_verification_details IS DISTINCT FROM OLD.replay_verification_details
                ) AND (
                    NEW.status = OLD.status
                    AND NEW.result_signature = OLD.result_signature
                    AND NEW.ranking_snapshot IS NOT DISTINCT FROM OLD.ranking_snapshot
                    AND NEW.finalized_at IS NOT DISTINCT FROM OLD.finalized_at
                    AND NEW.input_payload IS NOT DISTINCT FROM OLD.input_payload
                    AND NEW.random_seed IS NOT DISTINCT FROM OLD.random_seed
                ) THEN
                    RETURN NEW;
                END IF;

                RAISE EXCEPTION 'Finalized cases are immutable';
            END IF;

            RETURN NEW;
        END;
        $$;
        """
    ))


def downgrade() -> None:
    op.drop_constraint("chk_replay_only_on_finalized", "cases", type_="check")
    op.drop_column("cases", "replay_verification_details")
    op.drop_column("cases", "replay_verification_ok")
    op.drop_column("cases", "replay_verified_at")
