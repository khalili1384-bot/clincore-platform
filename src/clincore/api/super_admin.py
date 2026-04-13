"""
Super Admin API endpoints for tenant and API key management.
Requires X-Super-Admin-Key header for authentication.
"""
import os
import secrets
import hashlib
from typing import Any
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
import psycopg

router = APIRouter(prefix="/super-admin", tags=["super-admin"])

# Super admin key from environment
SUPER_ADMIN_KEY = os.getenv("SUPER_ADMIN_KEY", "super-secret-change-me")

# PostgreSQL connection string (same pattern as ratelimit.py)
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    _host = os.getenv("DB_HOST", "127.0.0.1")
    _port = os.getenv("DB_PORT", "5432")
    _user = os.getenv("DB_USER", "clincore_user")
    _pass = os.getenv("DB_PASSWORD", "")
    _name = os.getenv("DB_NAME", "clincore")
    DATABASE_URL = f"postgresql://{_user}:{_pass}@{_host}:{_port}/{_name}"


def verify_super_admin_key(request: Request):
    """Verify X-Super-Admin-Key header."""
    key = request.headers.get("X-Super-Admin-Key")
    if not key or key != SUPER_ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing X-Super-Admin-Key")


@router.post("/tenants")
async def create_tenant(request: Request, payload: dict[str, Any]):
    """Create a new tenant."""
    verify_super_admin_key(request)
    
    tenant_id = payload.get("tenant_id")
    name = payload.get("name")
    
    if not tenant_id or not name:
        return JSONResponse(status_code=400, content={"error": "tenant_id and name are required"})
    
    try:
        async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
            async with conn.cursor() as cur:
                insert_query = f"""
                    INSERT INTO tenants (id, name, created_at)
                    VALUES ('{tenant_id}', '{name}', now())
                """
                await cur.execute(insert_query)
                await conn.commit()
                return {"ok": True, "tenant_id": tenant_id}
    except psycopg.errors.UniqueViolation:
        return JSONResponse(status_code=409, content={"error": "tenant already exists"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/tenants")
async def list_tenants(request: Request):
    """List all tenants."""
    verify_super_admin_key(request)
    
    try:
        async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
            async with conn.cursor() as cur:
                query = "SELECT id, name, created_at FROM tenants ORDER BY created_at DESC"
                await cur.execute(query)
                rows = await cur.fetchall()
                tenants = [
                    {
                        "id": str(row[0]),
                        "name": row[1],
                        "created_at": row[2].isoformat() if row[2] else None
                    }
                    for row in rows
                ]
                return {"ok": True, "tenants": tenants}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.post("/api-keys")
async def create_api_key(request: Request, payload: dict[str, Any]):
    """Create a new API key for a tenant."""
    verify_super_admin_key(request)
    
    tenant_id = payload.get("tenant_id")
    role = payload.get("role", "doctor")
    
    if not tenant_id:
        return JSONResponse(status_code=400, content={"error": "tenant_id is required"})
    
    # Generate secure random key
    raw_key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    
    try:
        async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
            async with conn.cursor() as cur:
                insert_query = f"""
                    INSERT INTO api_keys (id, tenant_id, key_hash, role, is_active, created_at)
                    VALUES (gen_random_uuid(), '{tenant_id}', '{key_hash}', '{role}', true, now())
                """
                await cur.execute(insert_query)
                await conn.commit()
                return {"ok": True, "api_key": raw_key, "tenant_id": tenant_id}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.delete("/tenants/{tenant_id}")
async def deactivate_tenant(request: Request, tenant_id: str):
    """Deactivate all API keys for a tenant."""
    verify_super_admin_key(request)
    
    try:
        async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
            async with conn.cursor() as cur:
                update_query = f"""
                    UPDATE api_keys SET is_active = false
                    WHERE tenant_id = '{tenant_id}'
                """
                await cur.execute(update_query)
                await conn.commit()
                return {"ok": True, "deactivated": True}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
