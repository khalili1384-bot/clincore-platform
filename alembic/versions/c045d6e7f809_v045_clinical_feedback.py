"""
v045_clinical_feedback

Revision ID: c045d6e7f809
Revises: b1c2d3e4f505
Create Date: 2026-02-27 20:36:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = 'c045d6e7f809'
down_revision = 'b1c2d3e4f505'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create clinical_feedback table
    op.create_table(
        "clinical_feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("case_hash", sa.Text(), nullable=False),
        sa.Column("suggested_top1", sa.Text(), nullable=True),
        sa.Column("chosen_remedy", sa.Text(), nullable=False),
        sa.Column("chosen_rank", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Integer(), nullable=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )
    
    # Create index on tenant_id, created_at
    op.create_index("idx_clinical_feedback_tenant_time", "clinical_feedback", ["tenant_id", "created_at"])
    
    # Add comment for confidence range
    op.execute("COMMENT ON COLUMN clinical_feedback.confidence IS 'Physician confidence 1-5 scale'")


def downgrade() -> None:
    op.drop_index("idx_clinical_feedback_tenant_time", table_name="clinical_feedback")
    op.drop_table("clinical_feedback")
