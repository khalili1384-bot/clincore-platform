# -*- coding: utf-8 -*-
"""cases search index

Revision ID: 0056
Revises: 
Create Date: 2026-04-13 07:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0056'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        'idx_cases_tenant_status_created',
        'cases',
        ['tenant_id', 'status', 'created_at'],
        unique=False
    )
    op.create_index(
        'idx_cases_tenant_billing',
        'cases',
        ['tenant_id', 'billing_status'],
        unique=False
    )
    op.create_index(
        'idx_case_results_remedy',
        'case_results',
        ['remedy_name'],
        unique=False
    )
    op.create_index(
        'idx_cases_input_gin',
        'cases',
        ['input_payload'],
        unique=False,
        postgresql_using='gin'
    )


def downgrade() -> None:
    op.drop_index('idx_cases_input_gin', table_name='cases')
    op.drop_index('idx_case_results_remedy', table_name='case_results')
    op.drop_index('idx_cases_tenant_billing', table_name='cases')
    op.drop_index('idx_cases_tenant_status_created', table_name='cases')
