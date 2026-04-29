"""shop orders and stock

Revision ID: 0062
Revises: 0061
"""
from alembic import op
import sqlalchemy as sa

revision = "0062"
down_revision = "0061"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("shop_products", sa.Column("stock_quantity", sa.Integer(), nullable=False, server_default="100"))
    op.add_column("shop_products", sa.Column("stock_alert_threshold", sa.Integer(), nullable=False, server_default="5"))
    op.execute("""CREATE TABLE shop_orders (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        order_no TEXT NOT NULL UNIQUE,
        tenant_id UUID NOT NULL,
        customer_name TEXT NOT NULL,
        customer_phone TEXT NOT NULL,
        customer_address TEXT NOT NULL,
        patient_no TEXT,
        items JSONB NOT NULL DEFAULT "[]",
        total_amount NUMERIC(12,0) NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT "pending_payment",
        payment_method TEXT NOT NULL DEFAULT "card_to_card",
        payment_ref TEXT,
        notes TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )""".replace(chr(34), chr(39)))
    op.execute("CREATE INDEX idx_shop_orders_tenant ON shop_orders(tenant_id)")
    op.execute("CREATE INDEX idx_shop_orders_status ON shop_orders(status)")
    op.execute("CREATE INDEX idx_shop_orders_phone ON shop_orders(customer_phone)")

def downgrade():
    op.execute("DROP TABLE IF EXISTS shop_orders")
    op.drop_column("shop_products", "stock_alert_threshold")
    op.drop_column("shop_products", "stock_quantity")