"""
Tests for POST /bootstrap — tenant provisioning.
No external network required; uses ASGITransport + httpx.
"""
from __future__ import annotations

import asyncio
import os
import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from clincore.api.bootstrap import router as bootstrap_router
from clincore.db import engine


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def _make_app(bootstrap_token: str) -> FastAPI:
    os.environ["BOOTSTRAP_TOKEN"] = bootstrap_token
    # Re-import to pick up env var — router reads at call time, not import time
    from clincore.api import bootstrap as _bs_mod
    _bs_mod._BOOTSTRAP_TOKEN = bootstrap_token
    app = FastAPI()
    app.include_router(bootstrap_router)
    return app


@pytest.mark.asyncio
async def test_bootstrap_creates_tenant_and_key():
    token = "test-bootstrap-secret-" + uuid.uuid4().hex[:8]
    app = _make_app(token)

    transport = ASGITransport(app=app)
    tenant_name = f"bs_tenant_{uuid.uuid4().hex[:8]}"

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            "/bootstrap",
            json={"tenant_name": tenant_name},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert "tenant_id" in data
    assert "api_key" in data
    assert len(data["api_key"]) > 20

    # Verify tenant exists in DB
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text("SELECT id FROM tenants WHERE name = :name"),
                {"name": tenant_name},
            )
        ).fetchone()
    assert row is not None, f"Tenant '{tenant_name}' not found in DB"


@pytest.mark.asyncio
async def test_bootstrap_disabled_without_token():
    from clincore.api import bootstrap as _bs_mod
    original = _bs_mod._BOOTSTRAP_TOKEN
    _bs_mod._BOOTSTRAP_TOKEN = ""

    app = FastAPI()
    app.include_router(bootstrap_router)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            "/bootstrap",
            json={"tenant_name": "should_fail"},
            headers={"Authorization": "Bearer anything"},
        )

    _bs_mod._BOOTSTRAP_TOKEN = original
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_bootstrap_rejects_wrong_token():
    token = "correct-token-" + uuid.uuid4().hex[:8]
    app = _make_app(token)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            "/bootstrap",
            json={"tenant_name": "should_fail"},
            headers={"Authorization": "Bearer wrong-token"},
        )

    assert resp.status_code == 401
