"""
v033_finalize_signature_hardening

Revision ID: 9ab846c6a33b
Revises: 34bf50c7d602
Create Date: 2026-02-25 13:58:29.203284

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9ab846c6a33b'
down_revision = '34bf50c7d602'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "chk_finalized_requires_signature",
        "cases",
        "(status != 'finalized') OR (result_signature IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("chk_finalized_requires_signature", "cases", type_="check")
