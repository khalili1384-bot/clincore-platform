"""add patient_no sequential per tenant

Revision ID: 0061
Revises: 0060
Create Date: 2026-04-25
"""
from alembic import op
import sqlalchemy as sa

revision = '0061'
down_revision = '0060'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('patients', sa.Column('patient_no', sa.BigInteger(), nullable=True))
    # Set default value for existing rows (0 = legacy patient)
    op.execute("UPDATE patients SET patient_no = 0 WHERE patient_no IS NULL")

def downgrade():
    op.drop_column('patients', 'patient_no')