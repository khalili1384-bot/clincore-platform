"""Shop Orders API."""
import io
import csv
import json
import os
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel

router = APIRouter(tags=["shop-orders"])

SHOP_TENANT_ID = "c5e65972-36eb-42c6-ac46-8740593171bc"

VALID_STATUSES = {
    "pending_payment", "confirmed", "processing",
    "shipped", "delivered", "cancelled",
}


def _admin_key() -> str:
    return os.environ.get("SUPER_ADMIN_KEY", "")


def _card_number() -> str:
    return os.environ.get("SHOP_CARD_NUMBER", "")


async def _require_admin(x_super_admin_key: Optional[str] = Header(None)) -> str:
    if not x_super_admin_key or x_super_admin_key != _admin_key():
        raise HTTPException(status_code=401, detail="Unauthorized")
    return x_super_admin_key


try:
    from clincore.core.db import get_db
except ImportError:
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    _engine = create_async_engine(os.environ.get("DATABASE_URL", ""), echo=False)
    _factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

    async def get_db():
        async with _factory() as s:
            yield s


class OrderItem(BaseModel):
    product_id: str
    quantity: int


class CreateOrderRequest(BaseModel):
    customer_name: str
    customer_phone: str
    customer_address: str
    patient_no: Optional[str] = None
    notes: Optional[str] = None
    items: list[OrderItem]
    payment_method: str = "card_to_card"


class UpdateStatusRequest(BaseModel):
    status: str
    payment_ref: Optional[str] = None


async def _next_order_no(db: AsyncSession) -> str:
    tid = SHOP_TENANT_ID
    result = await db.execute(text(
        f"SELECT COALESCE(MAX(CAST(SUBSTRING(order_no FROM 5) AS INTEGER)), 0) + 1 "
        f"FROM shop_orders WHERE tenant_id = '{tid}'"
    ))
    num = result.scalar() or 1
    return f"ORD-{num:04d}"


@router.post("/shop/orders")
async def create_order(req: CreateOrderRequest, db: AsyncSession = Depends(get_db)):
    tid = SHOP_TENANT_ID
    await db.execute(text(f"SET LOCAL app.tenant_id = '{tid}'"))
    if not req.customer_name.strip():
        raise HTTPException(status_code=400, detail="نام الزامی است")
    if not req.customer_phone.strip():
        raise HTTPException(status_code=400, detail="موبایل الزامی است")
    if not req.customer_address.strip():
        raise HTTPException(status_code=400, detail="آدرس الزامی است")
    if not req.items:
        raise HTTPException(status_code=400, detail="سبد خرید خالی است")

    enriched_items = []
    for item in req.items:
        safe_pid = item.product_id.replace("'", "''")
        row = (await db.execute(text(
            f"SELECT id, name_fa, price, stock_quantity "
            f"FROM shop_products "
            f"WHERE id = '{safe_pid}' AND tenant_id = '{tid}' AND is_active = true"
        ))).fetchone()
        if not row:
            raise HTTPException(status_code=400, detail=f"محصول یافت نشد: {item.product_id}")
        stock = row.stock_quantity if row.stock_quantity is not None else 0
        if stock < item.quantity:
            raise HTTPException(status_code=400, detail=f"موجودی کافی نیست: {row.name_fa}")
        enriched_items.append({
            "product_id": str(row.id),
            "name_fa": row.name_fa,
            "quantity": item.quantity,
            "unit_price": float(row.price),
        })

    total = sum(it["unit_price"] * it["quantity"] for it in enriched_items)
    order_no = await _next_order_no(db)
    order_id = str(uuid.uuid4())
    items_json = json.dumps(enriched_items, ensure_ascii=False).replace("'", "''")

    safe_name = req.customer_name.strip().replace("'", "''")
    safe_phone = req.customer_phone.strip().replace("'", "''")
    safe_addr = req.customer_address.strip().replace("'", "''")
    safe_pno = (req.patient_no or "").strip().replace("'", "''")
    safe_notes = (req.notes or "").strip().replace("'", "''")
    safe_pay = req.payment_method.replace("'", "''")
    safe_ono = order_no.replace("'", "''")

    pno_sql = f"'{safe_pno}'" if safe_pno else "NULL"
    notes_sql = f"'{safe_notes}'" if safe_notes else "NULL"

    await db.execute(text(
        f"INSERT INTO shop_orders "
        f"(id, order_no, tenant_id, customer_name, customer_phone, "
        f"customer_address, patient_no, items, total_amount, "
        f"status, payment_method, notes, created_at, updated_at) "
        f"VALUES "
        f"('{order_id}', '{safe_ono}', '{tid}', "
        f"'{safe_name}', '{safe_phone}', '{safe_addr}', "
        f"{pno_sql}, '{items_json}'::jsonb, {total}, "
        f"'pending_payment', '{safe_pay}', {notes_sql}, NOW(), NOW())"
    ))
    await db.commit()
    return {
        "ok": True,
        "order_no": order_no,
        "order_id": order_id,
        "total_amount": total,
        "status": "pending_payment",
        "payment_method": req.payment_method,
        "card_number": _card_number() if req.payment_method == "card_to_card" else None,
    }


@router.get("/shop/orders")
async def list_orders(
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(_require_admin),
):
    tid = SHOP_TENANT_ID
    await db.execute(text(f"SET LOCAL app.tenant_id = '{tid}'"))
    where = f"WHERE tenant_id = '{tid}'"
    if status and status in VALID_STATUSES:
        safe_status = status.replace("'", "''")
        where += f" AND status = '{safe_status}'"
    offset = (page - 1) * page_size
    result = await db.execute(text(
        f"SELECT id, order_no, customer_name, customer_phone, customer_address, "
        f"patient_no, items, total_amount, status, payment_method, "
        f"payment_ref, notes, created_at, updated_at "
        f"FROM shop_orders {where} "
        f"ORDER BY created_at DESC LIMIT {page_size} OFFSET {offset}"
    ))
    orders = []
    for r in result.fetchall():
        orders.append({
            "id": str(r.id), "order_no": r.order_no,
            "customer_name": r.customer_name, "customer_phone": r.customer_phone,
            "customer_address": r.customer_address, "patient_no": r.patient_no,
            "items": r.items, "total_amount": float(r.total_amount),
            "status": r.status, "payment_method": r.payment_method,
            "payment_ref": r.payment_ref, "notes": r.notes,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        })
    return {"ok": True, "orders": orders}


@router.patch("/shop/orders/{order_id}/status")
async def update_order_status(
    order_id: str,
    req: UpdateStatusRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(_require_admin),
):
    if req.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="وضعیت نامعتبر است")
    tid = SHOP_TENANT_ID
    await db.execute(text(f"SET LOCAL app.tenant_id = '{tid}'"))
    safe_id = order_id.replace("'", "''")
    safe_status = req.status.replace("'", "''")
    safe_ref = (req.payment_ref or "").replace("'", "''")
    ref_sql = f"'{safe_ref}'" if safe_ref else "NULL"

    row = (await db.execute(text(
        f"SELECT status, items FROM shop_orders "
        f"WHERE id = '{safe_id}' AND tenant_id = '{tid}'"
    ))).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="سفارش یافت نشد")

    if req.status == "confirmed" and row.status == "pending_payment":
        items = row.items if isinstance(row.items, list) else json.loads(row.items or "[]")
        for item in items:
            pid = str(item["product_id"]).replace("'", "''")
            qty = int(item["quantity"])
            await db.execute(text(
                f"UPDATE shop_products "
                f"SET stock_quantity = GREATEST(0, stock_quantity - {qty}), updated_at = NOW() "
                f"WHERE id = '{pid}' AND tenant_id = '{tid}'"
            ))

    await db.execute(text(
        f"UPDATE shop_orders "
        f"SET status = '{safe_status}', payment_ref = {ref_sql}, updated_at = NOW() "
        f"WHERE id = '{safe_id}' AND tenant_id = '{tid}'"
    ))
    await db.commit()
    return {"ok": True, "status": req.status}


@router.get("/shop/export/mahak")
async def export_mahak(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(_require_admin),
):
    tid = SHOP_TENANT_ID
    await db.execute(text(f"SET LOCAL app.tenant_id = '{tid}'"))
    where = f"WHERE o.tenant_id = '{tid}'"
    if from_date:
        sf = from_date.replace("'", "''")
        where += f" AND o.created_at >= '{sf}'"
    if to_date:
        st = to_date.replace("'", "''")
        where += f" AND o.created_at < '{st}'::date + interval '1 day'"

    result = await db.execute(text(
        f"SELECT o.order_no, o.created_at, o.customer_name, o.customer_phone, "
        f"o.total_amount, o.status, o.items "
        f"FROM shop_orders o {where} ORDER BY o.created_at"
    ))
    rows = result.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["order_no", "date", "customer_name", "customer_phone",
                     "product_sku", "product_name", "quantity", "unit_price", "total", "status"])

    for r in rows:
        items = r.items if isinstance(r.items, list) else json.loads(r.items or "[]")
        date_str = r.created_at.strftime("%Y-%m-%d") if r.created_at else ""
        for item in items:
            pid = str(item.get("product_id", "")).replace("'", "''")
            sku_row = (await db.execute(text(
                f"SELECT sku FROM shop_products WHERE id = '{pid}'"
            ))).fetchone()
            sku = sku_row.sku if sku_row else ""
            line_total = float(item.get("unit_price", 0)) * int(item.get("quantity", 1))
            writer.writerow([
                r.order_no, date_str, r.customer_name, r.customer_phone,
                sku, item.get("name_fa", ""), item.get("quantity", 0),
                item.get("unit_price", 0), line_total, r.status,
            ])

    csv_bytes = b"\xef\xbb\xbf" + output.getvalue().encode("utf-8")
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": "attachment; filename=mahak_export.csv"},
    )
