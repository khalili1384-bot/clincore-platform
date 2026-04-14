"""
Auth API Keys endpoints — tenant-level key management.
Requires X-Super-Admin-Key for all operations.
"""
import os
import hashlib
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
import psycopg

router = APIRouter(prefix="/auth", tags=["auth"])

SUPER_ADMIN_KEY = os.getenv("SUPER_ADMIN_KEY", "")

DATABASE_URL = os.getenv("DATABASE_URL") or (
    f"postgresql://{os.getenv('DB_USER','clincore_user')}:"
    f"{os.getenv('DB_PASSWORD','')}@"
    f"{os.getenv('DB_HOST','127.0.0.1')}:"
    f"{os.getenv('DB_PORT','5432')}/"
    f"{os.getenv('DB_NAME','clincore')}"
)


def _verify(request: Request):
    key = request.headers.get("X-Super-Admin-Key", "")
    if not SUPER_ADMIN_KEY or key != SUPER_ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing X-Super-Admin-Key")


@router.get("/api-keys/{tenant_id}")
async def list_api_keys(request: Request, tenant_id: str):
    """List all API keys for a tenant (hashes only, not raw keys)."""
    _verify(request)
    try:
        async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    f"SELECT id, role, is_active, created_at FROM api_keys "
                    f"WHERE tenant_id = '{tenant_id}' ORDER BY created_at DESC"
                )
                rows = await cur.fetchall()
                return {
                    "ok": True,
                    "tenant_id": tenant_id,
                    "api_keys": [
                        {
                            "id": str(r[0]),
                            "role": r[1],
                            "is_active": r[2],
                            "created_at": r[3].isoformat() if r[3] else None,
                        }
                        for r in rows
                    ],
                }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.patch("/api-keys/{key_id}/deactivate")
async def deactivate_api_key(request: Request, key_id: str):
    """Deactivate a specific API key by its ID."""
    _verify(request)
    try:
        async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    f"UPDATE api_keys SET is_active = false WHERE id = '{key_id}'"
                )
                await conn.commit()
                return {"ok": True, "key_id": key_id, "is_active": False}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/usage/{tenant_id}")
async def tenant_usage(request: Request, tenant_id: str):
    """Show today's API usage per endpoint for a tenant."""
    _verify(request)
    try:
        async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    f"SELECT endpoint_path, COUNT(*) as count "
                    f"FROM usage_events "
                    f"WHERE tenant_id = '{tenant_id}' "
                    f"AND created_at >= date_trunc('day', now() AT TIME ZONE 'UTC') "
                    f"GROUP BY endpoint_path ORDER BY count DESC"
                )
                rows = await cur.fetchall()
                return {
                    "ok": True,
                    "tenant_id": tenant_id,
                    "usage_today": [
                        {"endpoint": r[0], "count": r[1]} for r in rows
                    ],
                }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
