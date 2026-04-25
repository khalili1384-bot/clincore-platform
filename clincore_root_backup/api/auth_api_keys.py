"""
API-key authentication helpers + router.
Provides FastAPI dependency get_api_key_tenant() for use in protected endpoints.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import secrets
import uuid

from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy import text

from clincore.db import engine as _engine, tenant_session

_log = logging.getLogger("clincore.auth")

router = APIRouter(prefix="/auth", tags=["auth"])


def _hash_key(raw_key: str) -> str:
    """SHA-256 hex of the raw key — deterministic, no salt (lookup token pattern)."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


async def _record_usage(tenant_id: str, api_key_id: str, endpoint: str) -> None:
    """Fire-and-forget INSERT into usage_events. Errors are logged, never raised."""
    try:
        async with tenant_session(tenant_id) as session:
            await session.execute(
                text(
                    """
                    INSERT INTO usage_events (tenant_id, api_key_id, endpoint, created_at)
                    VALUES (:tenant_id, :api_key_id, :endpoint, now())
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "api_key_id": api_key_id,
                    "endpoint": endpoint,
                },
            )
    except Exception as exc:
        _log.warning("usage_events insert failed: %s", exc)


async def get_api_key_tenant(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> str:
    """
    FastAPI dependency: validates X-API-Key header against api_keys table.
    Returns tenant_id (str) on success. Raises 401 on failure.
    Also inserts a usage_events row (fire-and-forget, never blocks).
    """
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")

    key_hash = _hash_key(x_api_key)

    async with _engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    """
                    SELECT id, tenant_id FROM api_keys
                    WHERE key_hash = :key_hash
                      AND is_active = true
                      AND revoked_at IS NULL
                    LIMIT 1
                    """
                ),
                {"key_hash": key_hash},
            )
        ).fetchone()

    if not row:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key")

    api_key_id = str(row[0])
    tenant_id = str(row[1])
    endpoint = str(request.url.path)

    asyncio.ensure_future(_record_usage(tenant_id, api_key_id, endpoint))

    return tenant_id


@router.post("/api-keys/rotate", tags=["auth"])
async def rotate_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    """
    Rotate the current API key: deactivate old, return new raw key.
    """
    tenant_id = await get_api_key_tenant(request, x_api_key)
    old_hash = _hash_key(x_api_key)

    new_raw = secrets.token_urlsafe(32)
    new_hash = _hash_key(new_raw)

    async with _engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE api_keys SET is_active = false WHERE key_hash = :old_hash"
            ),
            {"old_hash": old_hash},
        )
        await conn.execute(
            text(
                """
                INSERT INTO api_keys (id, tenant_id, key_hash, label, is_active, created_at)
                VALUES (:id, :tenant_id, :key_hash, 'rotated', true, now())
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "tenant_id": tenant_id,
                "key_hash": new_hash,
            },
        )

    return {"api_key": new_raw, "tenant_id": tenant_id}
