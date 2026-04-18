# -*- coding: utf-8 -*-
"""cases patient fk

Revision ID: 0057
Revises: 0056
Create Date: 2026-04-13 08:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '0057'
down_revision = '0056'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        'idx_cases_patient',
        'cases',
        ['patient_id'],
        unique=False
    )
    op.create_index(
        'ix_cases_tenant_id',
        'cases',
        ['tenant_id'],
        unique=False
    )
    op.create_index(
        'idx_case_results_case_rank',
        'case_results',
        ['case_id', 'rank'],
        unique=False
    )
    op.create_foreign_key(
        'fk_cases_patient_id',
        'cases', 'patients',
        ['patient_id'], ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    op.drop_constraint('fk_cases_patient_id', 'cases', type_='foreignkey')
    op.drop_index('idx_case_results_case_rank', table_name='case_results')
    op.drop_index('ix_cases_tenant_id', table_name='cases')
    op.drop_index('idx_cases_patient', table_name='cases')
