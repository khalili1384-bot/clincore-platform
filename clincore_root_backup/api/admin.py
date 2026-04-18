"""
Admin API — usage analytics + API key management.
All endpoints require a valid API key with role='admin'.
All queries are tenant-scoped (RLS enforced).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text

from clincore.api.auth_api_keys import get_api_key_tenant, _hash_key
from clincore.db import engine as _engine, tenant_session

router = APIRouter(prefix="/admin", tags=["admin"])


async def get_admin_tenant(
    request: Request,
    tenant_id: str = Depends(get_api_key_tenant),
) -> str:
    """
    Dependency: validates that the API key has role='admin'.
    Returns tenant_id on success.
    """
    x_api_key = request.headers.get("X-API-Key")
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    key_hash = _hash_key(x_api_key)

    async with _engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    """
                    SELECT role FROM api_keys
                    WHERE key_hash = :kh AND is_active = true AND revoked_at IS NULL
                    LIMIT 1
                    """
                ),
                {"kh": key_hash},
            )
        ).fetchone()

    if not row or row[0] != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")

    return tenant_id


@router.get("/usage")
async def get_usage(tenant_id: str = Depends(get_admin_tenant)):
    """Return aggregated usage_events stats for the calling tenant."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

    async with tenant_session(tenant_id) as session:
        total_row = (
            await session.execute(
                text("SELECT COUNT(*) FROM usage_events")
            )
        ).fetchone()

        by_endpoint = (
            await session.execute(
                text(
                    "SELECT endpoint, COUNT(*) AS cnt FROM usage_events "
                    "GROUP BY endpoint ORDER BY cnt DESC"
                )
            )
        ).fetchall()

        last24_row = (
            await session.execute(
                text(
                    "SELECT COUNT(*) FROM usage_events WHERE created_at >= :cutoff"
                ),
                {"cutoff": cutoff},
            )
        ).fetchone()

    return {
        "total_calls": total_row[0] if total_row else 0,
        "calls_by_endpoint": {r[0]: r[1] for r in by_endpoint},
        "last_24h_count": last24_row[0] if last24_row else 0,
    }


@router.get("/api-keys")
async def list_api_keys(tenant_id: str = Depends(get_admin_tenant)):
    """List active API keys for the calling tenant — no plaintext keys."""
    async with _engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    """
                    SELECT id, label, role, is_active, created_at, last_used_at, revoked_at
                    FROM api_keys
                    WHERE tenant_id = :tid AND revoked_at IS NULL
                    ORDER BY created_at DESC
                    """
                ),
                {"tid": tenant_id},
            )
        ).fetchall()

    return [
        {
            "id": str(r[0]),
            "label": r[1],
            "role": r[2],
            "is_active": r[3],
            "created_at": r[4].isoformat() if r[4] else None,
            "last_used_at": r[5].isoformat() if r[5] else None,
            "revoked_at": r[6].isoformat() if r[6] else None,
        }
        for r in rows
    ]


@router.post("/api-keys/revoke/{key_id}")
async def revoke_api_key(
    key_id: str,
    tenant_id: str = Depends(get_admin_tenant),
):
    """Revoke an API key by setting revoked_at = now(). Tenant-scoped."""
    async with _engine.begin() as conn:
        result = await conn.execute(
            text(
                """
                UPDATE api_keys
                SET revoked_at = now(), is_active = false
                WHERE id = :key_id AND tenant_id = :tid AND revoked_at IS NULL
                RETURNING id
                """
            ),
            {"key_id": key_id, "tid": tenant_id},
        )
        updated = result.fetchone()

    if not updated:
        raise HTTPException(status_code=404, detail="Key not found or already revoked")

    return {"revoked": str(updated[0])}
