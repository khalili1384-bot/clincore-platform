"""
Super Admin API endpoints.
Requires X-Super-Admin-Key header for authentication.
"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from clincore.core.config import settings
from clincore.core.database import session_scope
import psycopg

router = APIRouter(prefix="/super-admin", tags=["super-admin"])


def verify_super_admin_key(request: Request):
    """Verify X-Super-Admin-Key header. Missing or wrong → 401."""
    key = request.headers.get("X-Super-Admin-Key")
    if not key or not settings.SUPER_ADMIN_KEY or key != settings.SUPER_ADMIN_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Super-Admin-Key")


@router.get("/tenants")
async def list_tenants(request: Request):
    """List all distinct tenant_ids from api_keys table."""
    verify_super_admin_key(request)
    
    with session_scope() as conn:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT tenant_id FROM api_keys ORDER BY tenant_id")
        rows = cur.fetchall()
        tenants = [{"tenant_id": str(row[0])} for row in rows]
        return {"ok": True, "tenants": tenants}


@router.get("/tenants/{tenant_id}/usage")
async def tenant_usage(request: Request, tenant_id: str):
    """Count usage_events per endpoint for a tenant (today UTC)."""
    verify_super_admin_key(request)
    
    with session_scope() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT endpoint_path, COUNT(*) as count "
            f"FROM usage_events "
            f"WHERE tenant_id = '{tenant_id}' "
            f"AND created_at >= date_trunc('day', now() AT TIME ZONE 'UTC') "
            f"GROUP BY endpoint_path ORDER BY count DESC"
        )
        rows = cur.fetchall()
        usage = [{"endpoint": row[0], "count": row[1]} for row in rows]
        return {"ok": True, "tenant_id": tenant_id, "usage_today": usage}


@router.get("/api-keys")
async def list_api_keys(request: Request):
    """List all api_keys (id, tenant_id, role, is_active, created_at)."""
    verify_super_admin_key(request)
    
    with session_scope() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, tenant_id, role, is_active, created_at FROM api_keys ORDER BY created_at DESC"
        )
        rows = cur.fetchall()
        api_keys = [
            {
                "id": str(row[0]),
                "tenant_id": str(row[1]),
                "role": row[2],
                "is_active": row[3],
                "created_at": row[4].isoformat() if row[4] else None,
            }
            for row in rows
        ]
        return {"ok": True, "api_keys": api_keys}


@router.post("/api-keys/{key_id}/deactivate")
async def deactivate_api_key(request: Request, key_id: str):
    """Set is_active=False for an API key."""
    verify_super_admin_key(request)
    
    with session_scope() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE api_keys SET is_active = false WHERE id = '{key_id}'")
        conn.commit()
        return {"ok": True, "key_id": key_id, "is_active": False}


@router.post("/api-keys/{key_id}/activate")
async def activate_api_key(request: Request, key_id: str):
    """Set is_active=True for an API key."""
    verify_super_admin_key(request)
    
    with session_scope() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE api_keys SET is_active = true WHERE id = '{key_id}'")
        conn.commit()
        return {"ok": True, "key_id": key_id, "is_active": True}
