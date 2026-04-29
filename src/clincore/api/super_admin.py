import secrets
import hashlib
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from clincore.core.config import settings
from clincore.core.db import AsyncSessionLocal

router = APIRouter(prefix="/super-admin", tags=["super-admin"])


def _verify(request: Request):
    key = request.headers.get("X-Super-Admin-Key", "")
    if not settings.SUPER_ADMIN_KEY or key != settings.SUPER_ADMIN_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Super-Admin-Key")


class CreateApiKeyRequest(BaseModel):
    tenant_id: str
    role: str = "doctor"


@router.get("/tenants")
async def list_tenants(request: Request):
    _verify(request)
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT DISTINCT tenant_id FROM api_keys ORDER BY tenant_id"))
        rows = result.fetchall()
        return {"ok": True, "tenants": [{"tenant_id": str(r[0])} for r in rows]}


@router.get("/tenants/{tenant_id}/usage")
async def tenant_usage(request: Request, tenant_id: str):
    _verify(request)
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text(f"""
                SELECT endpoint_path, COUNT(*) as count FROM usage_events
                WHERE tenant_id = '{tenant_id}'
                AND created_at >= date_trunc('day', now() AT TIME ZONE 'UTC')
                GROUP BY endpoint_path ORDER BY count DESC
            """)
        )
        rows = result.fetchall()
        return {"ok": True, "tenant_id": tenant_id, "usage_today": [{"endpoint": r[0], "count": r[1]} for r in rows]}


@router.get("/api-keys")
async def list_api_keys(request: Request):
    _verify(request)
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT id, tenant_id, role, is_active, created_at FROM api_keys ORDER BY created_at DESC")
        )
        rows = result.fetchall()
        return {"ok": True, "api_keys": [
            {"id": str(r[0]), "tenant_id": str(r[1]), "role": r[2], "is_active": r[3],
             "created_at": r[4].isoformat() if r[4] else None}
            for r in rows
        ]}


@router.post("/api-keys/new")
async def create_api_key(request: Request, body: CreateApiKeyRequest):
    _verify(request)
    plain_key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(plain_key.encode()).hexdigest()
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text(f"""
                INSERT INTO api_keys (tenant_id, key_hash, role, is_active)
                VALUES ('{body.tenant_id}', '{key_hash}', '{body.role}', true)
                RETURNING id
            """)
        )
        row = result.fetchone()
        await session.commit()
        return {"ok": True, "id": str(row[0]), "tenant_id": body.tenant_id, "role": body.role, "api_key": plain_key}


@router.post("/api-keys/{key_id}/deactivate")
async def deactivate_api_key(request: Request, key_id: str):
    _verify(request)
    async with AsyncSessionLocal() as session:
        await session.execute(text(f"UPDATE api_keys SET is_active = false WHERE id = '{key_id}'"))
        await session.commit()
        return {"ok": True, "key_id": key_id, "is_active": False}


@router.post("/api-keys/{key_id}/activate")
async def activate_api_key(request: Request, key_id: str):
    _verify(request)
    async with AsyncSessionLocal() as session:
        await session.execute(text(f"UPDATE api_keys SET is_active = true WHERE id = '{key_id}'"))
        await session.commit()
        return {"ok": True, "key_id": key_id, "is_active": True}
