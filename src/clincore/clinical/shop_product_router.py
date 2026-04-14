"""
Shop Product API endpoints.
Public read (no auth). Admin write (X-Super-Admin-Key).
"""
import os
from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
import psycopg

router = APIRouter(prefix="/shop", tags=["shop"])

DATABASE_URL = os.getenv("DATABASE_URL") or (
    f"postgresql://{os.getenv('DB_USER','clincore_user')}:"
    f"{os.getenv('DB_PASSWORD','')}@"
    f"{os.getenv('DB_HOST','127.0.0.1')}:"
    f"{os.getenv('DB_PORT','5432')}/"
    f"{os.getenv('DB_NAME','clincore')}"
)
SUPER_ADMIN_KEY = os.getenv("SUPER_ADMIN_KEY", "")
SHOP_TENANT_ID = "c5e65972-36eb-42c6-ac46-8740593171bc"


@router.get("/products")
async def list_products(
    category: str = Query(None),
    search: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List all active shop products. Public endpoint."""
    try:
        async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    f"SET LOCAL app.tenant_id = '{SHOP_TENANT_ID}'"
                )
                where = f"WHERE is_active = true AND tenant_id = '{SHOP_TENANT_ID}'"
                if category:
                    where += f" AND category = '{category}'"
                if search:
                    where += (
                        f" AND (name ILIKE '%{search}%' OR name_fa ILIKE '%{search}%')"
                    )
                offset = (page - 1) * page_size
                count_row = await (
                    await cur.execute(f"SELECT COUNT(*) FROM shop_products {where}")
                ).fetchone()
                total = count_row[0] if count_row else 0
                await cur.execute(
                    f"SELECT id, name, name_fa, category, description, price, unit, sku, is_active "
                    f"FROM shop_products {where} "
                    f"ORDER BY category, name "
                    f"LIMIT {page_size} OFFSET {offset}"
                )
                rows = await cur.fetchall()
                products = [
                    {
                        "id": str(r[0]),
                        "name": r[1],
                        "name_fa": r[2],
                        "category": r[3],
                        "description": r[4],
                        "price": float(r[5]) if r[5] else 0,
                        "unit": r[6],
                        "sku": r[7],
                        "is_active": r[8],
                    }
                    for r in rows
                ]
                return {
                    "ok": True,
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                    "products": products,
                }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/products/categories")
async def list_categories():
    """List all product categories."""
    try:
        async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    f"SET LOCAL app.tenant_id = '{SHOP_TENANT_ID}'"
                )
                await cur.execute(
                    f"SELECT DISTINCT category, COUNT(*) as cnt "
                    f"FROM shop_products "
                    f"WHERE is_active = true AND tenant_id = '{SHOP_TENANT_ID}' "
                    f"GROUP BY category ORDER BY category"
                )
                rows = await cur.fetchall()
                return {
                    "ok": True,
                    "categories": [{"name": r[0], "count": r[1]} for r in rows],
                }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/products/{product_id}")
async def get_product(product_id: str):
    """Get single product by ID."""
    try:
        async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    f"SET LOCAL app.tenant_id = '{SHOP_TENANT_ID}'"
                )
                await cur.execute(
                    f"SELECT id, name, name_fa, category, description, price, unit, sku, is_active "
                    f"FROM shop_products "
                    f"WHERE id = '{product_id}' AND tenant_id = '{SHOP_TENANT_ID}'"
                )
                row = await cur.fetchone()
                if not row:
                    return JSONResponse(status_code=404, content={"error": "product not found"})
                return {
                    "ok": True,
                    "product": {
                        "id": str(row[0]),
                        "name": row[1],
                        "name_fa": row[2],
                        "category": row[3],
                        "description": row[4],
                        "price": float(row[5]) if row[5] else 0,
                        "unit": row[6],
                        "sku": row[7],
                        "is_active": row[8],
                    },
                }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.patch("/products/{product_id}/stock")
async def update_stock(request: Request, product_id: str):
    """Deactivate product when out of stock. Requires X-Super-Admin-Key."""
    key = request.headers.get("X-Super-Admin-Key", "")
    if not SUPER_ADMIN_KEY or key != SUPER_ADMIN_KEY:
        return JSONResponse(status_code=403, content={"error": "forbidden"})
    payload = await request.json()
    is_active = payload.get("is_active", True)
    try:
        async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    f"SET LOCAL app.tenant_id = '{SHOP_TENANT_ID}'"
                )
                await cur.execute(
                    f"UPDATE shop_products SET is_active = {is_active}, updated_at = now() "
                    f"WHERE id = '{product_id}' AND tenant_id = '{SHOP_TENANT_ID}'"
                )
                await conn.commit()
                return {"ok": True, "product_id": product_id, "is_active": is_active}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
