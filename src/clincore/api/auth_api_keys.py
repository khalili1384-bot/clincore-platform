from fastapi import APIRouter, Request, HTTPException
from sqlalchemy import text
from clincore.core.db import tenant_session
from clincore.core.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


def _verify(request: Request):
    key = request.headers.get("X-Super-Admin-Key", "")
    if not settings.SUPER_ADMIN_KEY or key != settings.SUPER_ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing X-Super-Admin-Key")


@router.get("/api-keys/{tenant_id}")
async def list_api_keys(request: Request, tenant_id: str):
    _verify(request)
    async with tenant_session(tenant_id) as session:
        result = await session.execute(
            text(
                "SELECT id, role, is_active, created_at "
                "FROM api_keys ORDER BY created_at DESC"
            )
        )
        rows = result.fetchall()
        return {"ok": True, "tenant_id": tenant_id, "api_keys": [
            {"id": str(r[0]), "role": r[1], "is_active": r[2],
             "created_at": r[3].isoformat() if r[3] else None}
            for r in rows
        ]}


@router.patch("/api-keys/{key_id}/deactivate")
async def deactivate_api_key(request: Request, key_id: str):
    _verify(request)
    async with tenant_session("system") as session:
        await session.execute(
            text("UPDATE api_keys SET is_active = false WHERE id = :kid"),
            {"kid": key_id},
        )
        await session.commit()
        return {"ok": True, "key_id": key_id, "is_active": False}


@router.get("/usage/{tenant_id}")
async def tenant_usage(request: Request, tenant_id: str):
    _verify(request)
    async with tenant_session(tenant_id) as session:
        result = await session.execute(
            text(
                "SELECT endpoint_path, COUNT(*) as count FROM usage_events "
                "WHERE created_at >= date_trunc('day', now() AT TIME ZONE 'UTC') "
                "GROUP BY endpoint_path ORDER BY count DESC"
            )
        )
        rows = result.fetchall()
        return {"ok": True, "tenant_id": tenant_id, "usage_today": [
            {"endpoint": r[0], "count": r[1]} for r in rows
        ]}
