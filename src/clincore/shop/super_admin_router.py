import os
from uuid import UUID
from typing import Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Header, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import text
from pydantic import BaseModel

from clincore.core.db import tenant_session as _tenant_session

SHOP_TENANT_ID = "c5e65972-36eb-42c6-ac46-8740593171bc"

async def get_db():
    async with _tenant_session(SHOP_TENANT_ID) as s:
        yield s

router = APIRouter(prefix="/super-admin", tags=["super-admin"])

VALID_STATUSES = {"pending_payment","confirmed","processing","shipped","delivered","cancelled"}

def _admin_key() -> str:
    return os.environ.get("SUPER_ADMIN_KEY", "")

def sanitize(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("'", "")

async def require_admin(x_super_admin_key: Optional[str] = Header(None)) -> str:
    key = _admin_key()
    if not key or not x_super_admin_key or x_super_admin_key != key:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return x_super_admin_key

async def _set_tenant(db: AsyncSession):
    pass

class ProductUpdate(BaseModel):
    price: Optional[float] = None
    name_fa: Optional[str] = None
    stock_quantity: Optional[int] = None
    is_active: Optional[bool] = None
    description: Optional[str] = None

class OrderStatusUpdate(BaseModel):
    status: str
    payment_ref: Optional[str] = None

# --- Products ---

@router.get("/products")
async def get_products(
    page: int = Query(1, ge=1),
    pagesize: int = Query(50, ge=1, le=100),
    search: str = Query(""),
    category: str = Query(""),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_admin),
):
    await _set_tenant(db)
    offset = (page - 1) * pagesize
    s = sanitize(search)
    c = sanitize(category)
    where = f"tenant_id = '{SHOP_TENANT_ID}'"
    if s:
        where += f" AND (name ILIKE '%{s}%' OR name_fa ILIKE '%{s}%' OR sku ILIKE '%{s}%')"
    if c:
        where += f" AND category = '{c}'"

    total = (await db.execute(text(f"SELECT COUNT(*) FROM shop_products WHERE {where}"))).scalar() or 0
    rows = (await db.execute(text(
        f"SELECT id, name, name_fa, category, price, unit, sku, stock_quantity, is_active, description "
        f"FROM shop_products WHERE {where} ORDER BY name LIMIT {pagesize} OFFSET {offset}"
    ))).fetchall()
    return {"ok": True, "total": total, "products": [dict(r._mapping) for r in rows]}

@router.patch("/products/{product_id}")
async def update_product(
    product_id: UUID,
    payload: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_admin),
):
    await _set_tenant(db)
    data = payload.dict(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    parts = ["updated_at = NOW()"]
    for k, v in data.items():
        if isinstance(v, str):
            parts.append(f"{k} = '{sanitize(v)}'")
        elif v is None:
            parts.append(f"{k} = NULL")
        else:
            parts.append(f"{k} = {v}")
    row = (await db.execute(text(
        f"UPDATE shop_products SET {', '.join(parts)} "
        f"WHERE id = '{product_id}' AND tenant_id = '{SHOP_TENANT_ID}' RETURNING id"
    ))).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    await db.commit()
    return {"ok": True, "updated": str(row[0])}

# --- Orders ---

@router.get("/orders")
async def get_orders(
    page: int = Query(1, ge=1),
    pagesize: int = Query(50, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_admin),
):
    await _set_tenant(db)
    offset = (page - 1) * pagesize
    where = f"tenant_id = '{SHOP_TENANT_ID}'"
    if status_filter and status_filter in VALID_STATUSES:
        where += f" AND status = '{status_filter}'"

    total = (await db.execute(text(f"SELECT COUNT(*) FROM shop_orders WHERE {where}"))).scalar() or 0
    rows = (await db.execute(text(
        f"SELECT id, order_no, customer_name, customer_phone, customer_address, "
        f"patient_no, items, total_amount, status, payment_method, payment_ref, notes, created_at, updated_at "
        f"FROM shop_orders WHERE {where} ORDER BY created_at DESC LIMIT {pagesize} OFFSET {offset}"
    ))).fetchall()
    orders = []
    for r in rows:
        d = dict(r._mapping)
        d["created_at"] = d["created_at"].isoformat() if d.get("created_at") else None
        d["updated_at"] = d["updated_at"].isoformat() if d.get("updated_at") else None
        orders.append(d)
    return {"ok": True, "total": total, "orders": orders}

@router.patch("/orders/{order_id}/status")
async def update_order_status(
    order_id: UUID,
    payload: OrderStatusUpdate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_admin),
):
    await _set_tenant(db)
    if payload.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Valid: {VALID_STATUSES}")
    s = sanitize(payload.status)
    parts = [f"status = '{s}'", "updated_at = NOW()"]
    if payload.payment_ref is not None:
        parts.append(f"payment_ref = '{sanitize(payload.payment_ref)}'")
    row = (await db.execute(text(
        f"UPDATE shop_orders SET {', '.join(parts)} "
        f"WHERE id = '{order_id}' AND tenant_id = '{SHOP_TENANT_ID}' RETURNING status"
    ))).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Order not found")
    await db.commit()
    return {"ok": True, "status": row[0]}

@router.delete("/orders/{order_id}")
async def delete_order(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_admin),
):
    await _set_tenant(db)
    row = (await db.execute(text(
        f"DELETE FROM shop_orders WHERE id = '{order_id}' AND tenant_id = '{SHOP_TENANT_ID}' RETURNING id"
    ))).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Order not found")
    await db.commit()
    return {"ok": True, "deleted": str(row[0])}



