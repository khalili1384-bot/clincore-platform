"""
Tests for API key auth dependency and /auth/api-keys/rotate endpoint.
No external network required; uses ASGITransport + httpx.
"""
from __future__ import annotations

import asyncio
import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from clincore.api.auth_api_keys import _hash_key, get_api_key_tenant, router as auth_router
from clincore.db import engine


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


async def _create_tenant_and_key(raw_key: str) -> str:
    """Helper: insert a tenant + api_key row directly. Returns tenant_id str."""
    tenant_id = str(uuid.uuid4())
    key_hash = _hash_key(raw_key)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO tenants (id, name, created_at) VALUES (:id, :name, now())"
            ),
            {"id": tenant_id, "name": f"auth_test_{uuid.uuid4().hex[:8]}"},
        )
        await conn.execute(
            text(
                """
                INSERT INTO api_keys (id, tenant_id, key_hash, label, is_active, created_at)
                VALUES (:id, :tenant_id, :key_hash, 'test-key', true, now())
                """
            ),
            {"id": str(uuid.uuid4()), "tenant_id": tenant_id, "key_hash": key_hash},
        )
    return tenant_id


@pytest.mark.asyncio
async def test_valid_api_key_resolves_tenant():
    raw_key = secrets_key()
    tenant_id = await _create_tenant_and_key(raw_key)

    resolved = await get_api_key_tenant(x_api_key=raw_key)
    assert resolved == tenant_id


@pytest.mark.asyncio
async def test_invalid_api_key_raises_401():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await get_api_key_tenant(x_api_key="totally-wrong-key")
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_missing_api_key_raises_401():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await get_api_key_tenant(x_api_key=None)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_rotate_key_via_endpoint():
    raw_key = secrets_key()
    tenant_id = await _create_tenant_and_key(raw_key)

    app = FastAPI()
    app.include_router(auth_router)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            "/auth/api-keys/rotate",
            headers={"X-API-Key": raw_key},
        )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "api_key" in data
    assert data["api_key"] != raw_key
    assert data["tenant_id"] == tenant_id

    # Old key must now be inactive
    old_hash = _hash_key(raw_key)
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT is_active FROM api_keys WHERE key_hash = :h"
                ),
                {"h": old_hash},
            )
        ).fetchone()
    assert row is not None
    assert row[0] is False, "Old key should be deactivated after rotation"


@pytest.mark.asyncio
async def test_inactive_key_rejected():
    raw_key = secrets_key()
    tenant_id = await _create_tenant_and_key(raw_key)
    key_hash = _hash_key(raw_key)

    # Deactivate directly
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE api_keys SET is_active = false WHERE key_hash = :h"),
            {"h": key_hash},
        )

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await get_api_key_tenant(x_api_key=raw_key)
    assert exc_info.value.status_code == 401


def secrets_key() -> str:
    import secrets
    return secrets.token_urlsafe(32)
