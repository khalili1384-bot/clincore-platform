"""Shop Product API - read public, write admin."""
import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

router = APIRouter(tags=["shop-products"])

SHOP_TENANT_ID = "c5e65972-36eb-42c6-ac46-8740593171bc"


def _admin_key() -> str:
    return os.environ.get("SUPER_ADMIN_KEY", "")


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


@router.get("/shop/products/categories")
async def list_categories(db: AsyncSession = Depends(get_db)):
    tid = SHOP_TENANT_ID
    await db.execute(text(f"SET LOCAL app.tenant_id = '{tid}'"))
    result = await db.execute(text(
        f"SELECT category, COUNT(*) as cnt FROM shop_products "
        f"WHERE tenant_id = '{tid}' AND is_active = true "
        f"GROUP BY category ORDER BY category"
    ))
    return {"ok": True, "categories": [{"name": r.category, "count": r.cnt} for r in result.fetchall()]}


@router.get("/shop/products")
async def list_products(
    category: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    tid = SHOP_TENANT_ID
    await db.execute(text(f"SET LOCAL app.tenant_id = '{tid}'"))
    where = f"WHERE tenant_id = '{tid}' AND is_active = true"
    if category:
        safe_cat = category.replace("'", "''")
        where += f" AND category = '{safe_cat}'"
    if search:
        s = search.replace("'", "''")
        where += f" AND (name ILIKE '%{s}%' OR name_fa ILIKE '%{s}%')"
    count_result = await db.execute(text(f"SELECT COUNT(*) FROM shop_products {where}"))
    total = count_result.scalar() or 0
    offset = (page - 1) * page_size
    result = await db.execute(text(
        f"SELECT id, name, name_fa, category, description, price, unit, sku, "
        f"stock_quantity, stock_alert_threshold "
        f"FROM shop_products {where} "
        f"ORDER BY category, name_fa LIMIT {page_size} OFFSET {offset}"
    ))
    products = []
    for r in result.fetchall():
        qty = r.stock_quantity if r.stock_quantity is not None else 0
        thr = r.stock_alert_threshold if r.stock_alert_threshold is not None else 5
        products.append({
            "id": str(r.id), "name": r.name, "name_fa": r.name_fa,
            "category": r.category, "description": r.description,
            "price": float(r.price), "unit": r.unit, "sku": r.sku,
            "stock_quantity": qty, "stock_alert_threshold": thr,
        })
    return {"ok": True, "total": total, "page": page, "page_size": page_size, "products": products}


@router.get("/shop/products/admin-list")
async def admin_list(db: AsyncSession = Depends(get_db), _: str = Depends(_require_admin)):
    tid = SHOP_TENANT_ID
    await db.execute(text(f"SET LOCAL app.tenant_id = '{tid}'"))
    result = await db.execute(text(
        f"SELECT id, name, name_fa, category, description, price, unit, sku, "
        f"is_active, stock_quantity, stock_alert_threshold "
        f"FROM shop_products WHERE tenant_id = '{tid}' ORDER BY category, name_fa"
    ))
    products = []
    for r in result.fetchall():
        qty = r.stock_quantity if r.stock_quantity is not None else 0
        thr = r.stock_alert_threshold if r.stock_alert_threshold is not None else 5
        products.append({
            "id": str(r.id), "name": r.name, "name_fa": r.name_fa,
            "category": r.category, "price": float(r.price),
            "unit": r.unit, "sku": r.sku, "is_active": r.is_active,
            "stock_quantity": qty, "stock_alert_threshold": thr,
            "description": r.description or "", "low_stock": 0 < qty <= thr, "out_of_stock": qty <= 0,
        })
    return {"ok": True, "products": products}


@router.put("/shop/products/{product_id}/stock")
async def update_stock(
    product_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(_require_admin),
):
    tid = SHOP_TENANT_ID
    await db.execute(text(f"SET LOCAL app.tenant_id = '{tid}'"))
    qty = int(body.get("stock_quantity", 0))
    thr = int(body.get("stock_alert_threshold", 5))
    safe_id = product_id.replace("'", "''")
    await db.execute(text(
        f"UPDATE shop_products "
        f"SET stock_quantity = {qty}, stock_alert_threshold = {thr}, updated_at = NOW() "
        f"WHERE id = '{safe_id}' AND tenant_id = '{tid}'"
    ))
    await db.commit()
    return {"ok": True}


@router.patch("/shop/products/{product_id}")
async def update_product(
    product_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(_require_admin),
):
    tid = SHOP_TENANT_ID
    await db.execute(text(f"SET LOCAL app.tenant_id = '{tid}'"))
    safe_id = product_id.replace("'", "''")
    updates = []
    if "price" in body:
        updates.append(f"price = {float(body['price'])}")
    if "stock_quantity" in body:
        updates.append(f"stock_quantity = {int(body['stock_quantity'])}")
    if "stock_alert_threshold" in body:
        updates.append(f"stock_alert_threshold = {int(body['stock_alert_threshold'])}")
    if "is_active" in body:
        val = "true" if body["is_active"] else "false"
        updates.append(f"is_active = {val}")
    if not updates:
        raise HTTPException(status_code=400, detail="هیچ فیلدی برای به‌روزرسانی نیست")
    updates.append("updated_at = NOW()")
    set_clause = ", ".join(updates)
    await db.execute(text(
        f"UPDATE shop_products SET {set_clause} "
        f"WHERE id = '{safe_id}' AND tenant_id = '{tid}'"
    ))
    await db.commit()
    return {"ok": True}


@router.post("/shop/products")
async def create_product(
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(_require_admin),
):
    tid = SHOP_TENANT_ID
    await db.execute(text(f"SET LOCAL app.tenant_id = '{tid}'"))
    import uuid; pid = str(uuid.uuid4())
    def esc(v): return str(v or "").replace("'", "''")
    name  = esc(body.get("name",  ""));  name_fa = esc(body.get("name_fa", ""))
    cat   = esc(body.get("category", "")); desc  = esc(body.get("description", ""))
    unit  = esc(body.get("unit", "عدد")); sku = esc(body.get("sku", ""))
    price = float(body.get("price", 0)); stock = int(body.get("stock_quantity", 0))
    thr   = int(body.get("stock_alert_threshold", 5))
    ia    = "true" if body.get("is_active", True) else "false"
    d_sql = f"'{desc}'" if desc else "NULL"
    s_sql = f"'{sku}'"  if sku  else "NULL"
    if not name or not name_fa or not cat:
        raise HTTPException(status_code=422, detail="name, name_fa, category required")
    await db.execute(text(
        f"INSERT INTO shop_products "
        f"(id,tenant_id,name,name_fa,category,description,"
        f"price,unit,sku,stock_quantity,stock_alert_threshold,is_active,created_at,updated_at) "
        f"VALUES ('{pid}','{tid}','{name}','{name_fa}','{cat}',"
        f"{d_sql},{price},'{unit}',{s_sql},{stock},{thr},{ia},NOW(),NOW())"
    ))
    await db.commit()
    return {"ok": True, "id": pid}


@router.delete("/shop/products/{product_id}")
async def delete_product(
    product_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(_require_admin),
):
    tid = SHOP_TENANT_ID
    await db.execute(text(f"SET LOCAL app.tenant_id = '{tid}'"))
    sid = product_id.replace("'", "''")
    r = await db.execute(text(
        f"DELETE FROM shop_products WHERE id='{sid}' AND tenant_id='{tid}'"
    ))
    await db.commit()
    if r.rowcount == 0: raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}


@router.patch("/shop/products/{product_id}")
async def patch_product(
    product_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(_require_admin),
):
    tid = SHOP_TENANT_ID
    await db.execute(text(f"SET LOCAL app.tenant_id = '{tid}'"))
    def esc(v): return str(v or "").replace("'", "''")
    sid = product_id.replace("'", "''")
    sets = []
    if "name"     in body: sets.append(f"name='{esc(body['name'])}'")
    if "name_fa"  in body: sets.append(f"name_fa='{esc(body['name_fa'])}'")
    if "category" in body: sets.append(f"category='{esc(body['category'])}'")
    if "description" in body:
        d = esc(body["description"])
        sets.append(f"description='{d}'" if d else "description=NULL")
    if "price"    in body: sets.append(f"price={float(body['price'])}")
    if "unit"     in body: sets.append(f"unit='{esc(body['unit'])}'")
    if "sku"      in body:
        s = esc(body["sku"])
        sets.append(f"sku='{s}'" if s else "sku=NULL")
    if "stock_quantity"       in body: sets.append(f"stock_quantity={int(body['stock_quantity'])}")
    if "stock_alert_threshold" in body: sets.append(f"stock_alert_threshold={int(body['stock_alert_threshold'])}")
    if "is_active" in body:
        ia = "true" if body["is_active"] else "false"
        sets.append(f"is_active={ia}")
    if not sets:
        raise HTTPException(status_code=422, detail="no fields to update")
    sets.append("updated_at=NOW()")
    set_clause = ", ".join(sets)
    r = await db.execute(text(
        f"UPDATE shop_products SET {set_clause} "
        f"WHERE id='{sid}' AND tenant_id='{tid}'"
    ))
    await db.commit()
    if r.rowcount == 0: raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}
