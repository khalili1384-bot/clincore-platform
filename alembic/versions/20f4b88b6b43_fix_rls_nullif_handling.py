"""
fix rls nullif handling

Revision ID: 20f4b88b6b43
Revises: 0001_core_init
Create Date: 2026-02-20 21:33:30.191469

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20f4b88b6b43'
down_revision = "0001_core_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
