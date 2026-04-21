from fastapi import APIRouter, Request, HTTPException
from clincore.core.config import settings
from clincore.core.database import session_scope

router = APIRouter(prefix="/super-admin", tags=["super-admin"])


def verify_super_admin_key(request: Request):
    key = request.headers.get("X-Super-Admin-Key")
    if not key or not settings.SUPER_ADMIN_KEY or key != settings.SUPER_ADMIN_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Super-Admin-Key")


@router.get("/tenants")
async def list_tenants(request: Request):
    verify_super_admin_key(request)
    with session_scope() as conn:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT tenant_id FROM api_keys ORDER BY tenant_id")
        rows = cur.fetchall()
        return {"ok": True, "tenants": [{"tenant_id": str(r[0])} for r in rows]}


@router.get("/tenants/{tenant_id}/usage")
async def tenant_usage(request: Request, tenant_id: str):
    verify_super_admin_key(request)
    with session_scope() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT endpoint_path, COUNT(*) as count FROM usage_events "
            "WHERE tenant_id = %s "
            "AND created_at >= date_trunc('day', now() AT TIME ZONE 'UTC') "
            "GROUP BY endpoint_path ORDER BY count DESC",
            (tenant_id,),
        )
        rows = cur.fetchall()
        return {"ok": True, "tenant_id": tenant_id, "usage_today": [{"endpoint": r[0], "count": r[1]} for r in rows]}


@router.get("/api-keys")
async def list_api_keys(request: Request):
    verify_super_admin_key(request)
    with session_scope() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, tenant_id, role, is_active, created_at FROM api_keys ORDER BY created_at DESC"
        )
        rows = cur.fetchall()
        return {"ok": True, "api_keys": [
            {"id": str(r[0]), "tenant_id": str(r[1]), "role": r[2], "is_active": r[3],
             "created_at": r[4].isoformat() if r[4] else None}
            for r in rows
        ]}


@router.post("/api-keys/{key_id}/deactivate")
async def deactivate_api_key(request: Request, key_id: str):
    verify_super_admin_key(request)
    with session_scope() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE api_keys SET is_active = false WHERE id = %s", (key_id,))
        conn.commit()
        return {"ok": True, "key_id": key_id, "is_active": False}


@router.post("/api-keys/{key_id}/activate")
async def activate_api_key(request: Request, key_id: str):
    verify_super_admin_key(request)
    with session_scope() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE api_keys SET is_active = true WHERE id = %s", (key_id,))
        conn.commit()
        return {"ok": True, "key_id": key_id, "is_active": True}
