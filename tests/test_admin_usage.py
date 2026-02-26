"""
Tests for Admin API + Usage Tracking (v0.3.7).
No external network required; uses ASGITransport + httpx.
"""
from __future__ import annotations

import asyncio
import secrets
import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from clincore.api.admin import router as admin_router
from clincore.api.auth_api_keys import _hash_key, router as auth_router
from clincore.api.case_engine import router as case_router
from clincore.db import engine, tenant_session


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _setup_tenant_with_admin_key() -> tuple[str, str, str]:
    """
    Create a tenant + admin api_key.
    Returns (tenant_id, api_key_id, raw_key).
    """
    tenant_id = str(uuid.uuid4())
    raw_key = secrets.token_urlsafe(32)
    key_hash = _hash_key(raw_key)
    key_id = str(uuid.uuid4())

    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO tenants (id, name, created_at) VALUES (:id, :name, now())"),
            {"id": tenant_id, "name": f"admin_test_{uuid.uuid4().hex[:8]}"},
        )
        await conn.execute(
            text(
                """
                INSERT INTO api_keys (id, tenant_id, key_hash, label, is_active, role, created_at)
                VALUES (:id, :tid, :kh, 'admin-key', true, 'admin', now())
                """
            ),
            {"id": key_id, "tid": tenant_id, "kh": key_hash},
        )
    return tenant_id, key_id, raw_key


async def _insert_usage_events(tenant_id: str, api_key_id: str, endpoint: str, count: int) -> None:
    """Directly insert N usage_events rows for a tenant (bypasses RLS via superuser conn)."""
    async with engine.begin() as conn:
        await conn.execute(
            text(f"SET app.tenant_id = '{tenant_id}'")
        )
        for _ in range(count):
            await conn.execute(
                text(
                    """
                    INSERT INTO usage_events (tenant_id, api_key_id, endpoint, created_at)
                    VALUES (:tid, :kid, :ep, now())
                    """
                ),
                {"tid": tenant_id, "kid": api_key_id, "ep": endpoint},
            )


def _admin_app() -> FastAPI:
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(admin_router)
    return app


def _case_app() -> FastAPI:
    app = FastAPI()
    app.include_router(case_router)
    return app


# ---------------------------------------------------------------------------
# STEP 4 Test 1: N usage_events after N API calls
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_usage_events_count_matches_calls():
    """Insert 3 usage_events directly → count should equal 3."""
    tenant_id, key_id, raw_key = await _setup_tenant_with_admin_key()
    await _insert_usage_events(tenant_id, key_id, "/test/endpoint", 3)

    async with tenant_session(tenant_id) as session:
        row = (
            await session.execute(
                text("SELECT COUNT(*) FROM usage_events")
            )
        ).fetchone()

    assert row[0] == 3


# ---------------------------------------------------------------------------
# STEP 4 Test 2: GET /admin/usage returns correct aggregated counts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_usage_aggregation():
    tenant_id, key_id, raw_key = await _setup_tenant_with_admin_key()
    await _insert_usage_events(tenant_id, key_id, "/cases", 5)
    await _insert_usage_events(tenant_id, key_id, "/auth/api-keys/rotate", 2)

    transport = ASGITransport(app=_admin_app())
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get(
            "/admin/usage",
            headers={"X-API-Key": raw_key},
        )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total_calls"] == 7
    assert data["calls_by_endpoint"]["/cases"] == 5
    assert data["calls_by_endpoint"]["/auth/api-keys/rotate"] == 2
    assert "last_24h_count" in data
    assert data["last_24h_count"] == 7


# ---------------------------------------------------------------------------
# STEP 4 Test 3: Revoked key cannot call API
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_revoked_key_rejected():
    tenant_id, key_id, raw_key = await _setup_tenant_with_admin_key()

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE api_keys SET revoked_at = now(), is_active = false WHERE id = :kid"
            ),
            {"kid": key_id},
        )

    transport = ASGITransport(app=_admin_app())
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/admin/usage", headers={"X-API-Key": raw_key})

    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# STEP 4 Test 4: Tenant isolation — Tenant A cannot see Tenant B usage
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_usage_tenant_isolation():
    tenant_a_id, key_a_id, raw_key_a = await _setup_tenant_with_admin_key()
    tenant_b_id, key_b_id, raw_key_b = await _setup_tenant_with_admin_key()

    await _insert_usage_events(tenant_a_id, key_a_id, "/cases", 10)
    await _insert_usage_events(tenant_b_id, key_b_id, "/cases", 3)

    transport = ASGITransport(app=_admin_app())
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp_a = await client.get("/admin/usage", headers={"X-API-Key": raw_key_a})
        resp_b = await client.get("/admin/usage", headers={"X-API-Key": raw_key_b})

    assert resp_a.status_code == 200, resp_a.text
    assert resp_b.status_code == 200, resp_b.text

    assert resp_a.json()["total_calls"] == 10
    assert resp_b.json()["total_calls"] == 3


# ---------------------------------------------------------------------------
# STEP 4 Test 5: List API keys
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_api_keys():
    tenant_id, key_id, raw_key = await _setup_tenant_with_admin_key()

    transport = ASGITransport(app=_admin_app())
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/admin/api-keys", headers={"X-API-Key": raw_key})

    assert resp.status_code == 200, resp.text
    keys = resp.json()
    assert len(keys) >= 1
    # No plaintext key exposed
    for k in keys:
        assert "key_hash" not in k
        assert "id" in k
        assert k["role"] in ("admin", "user")


# ---------------------------------------------------------------------------
# STEP 4 Test 6: Revoke key via endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_revoke_key_via_endpoint():
    tenant_id, key_id, raw_key = await _setup_tenant_with_admin_key()

    second_raw = secrets.token_urlsafe(32)
    second_id = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO api_keys (id, tenant_id, key_hash, label, is_active, role, created_at)
                VALUES (:id, :tid, :kh, 'to-revoke', true, 'user', now())
                """
            ),
            {"id": second_id, "tid": tenant_id, "kh": _hash_key(second_raw)},
        )

    transport = ASGITransport(app=_admin_app())
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            f"/admin/api-keys/revoke/{second_id}",
            headers={"X-API-Key": raw_key},
        )

    assert resp.status_code == 200, resp.text
    assert resp.json()["revoked"] == second_id

    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text("SELECT revoked_at, is_active FROM api_keys WHERE id = :id"),
                {"id": second_id},
            )
        ).fetchone()
    assert row[0] is not None, "revoked_at should be set"
    assert row[1] is False, "is_active should be False"


# ---------------------------------------------------------------------------
# STEP 5: Billing guard — free tier > 1000 usage_events → 402 on case creation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_billing_guard_free_tier_soft_limit():
    """
    Simulate a free-tier tenant with > 1000 usage_events.
    POST /cases must return 402.
    """
    tenant_id = str(uuid.uuid4())
    patient_id = str(uuid.uuid4())

    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO tenants (id, name, created_at) VALUES (:id, :name, now())"),
            {"id": tenant_id, "name": f"billing_test_{uuid.uuid4().hex[:6]}"},
        )

    async with tenant_session(tenant_id) as session:
        await session.execute(
            text(
                "INSERT INTO patients (id, tenant_id, full_name, created_at) "
                "VALUES (:id, :tid, 'Billing Guard Patient', now())"
            ),
            {"id": patient_id, "tid": tenant_id},
        )
        # Create one case first so billing_status='free' row exists
        await session.execute(
            text(
                """
                INSERT INTO cases (id, tenant_id, input_payload, random_seed, status, created_at)
                VALUES (:id, :tid, '{"symptom_ids":[1]}'::jsonb, '0', 'draft', now())
                """
            ),
            {"id": str(uuid.uuid4()), "tid": tenant_id},
        )
        await session.flush()

    # Insert 1001 usage_events directly
    api_key_id = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(text(f"SET app.tenant_id = '{tenant_id}'"))
        # Batch insert for speed
        rows = ", ".join(
            f"('{tenant_id}', '{api_key_id}', '/cases', now())"
            for _ in range(1001)
        )
        await conn.execute(
            text(
                f"INSERT INTO usage_events (tenant_id, api_key_id, endpoint, created_at) VALUES {rows}"
            )
        )

    transport = ASGITransport(app=_case_app())
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            "/cases",
            headers={"X-Tenant-ID": tenant_id},
            json={"patient_id": patient_id, "input_payload": {"symptom_ids": [1]}},
        )

    assert resp.status_code == 402, (
        f"Expected 402 for free-tier over limit, got {resp.status_code}: {resp.text}"
    )
