"""
tests/test_prod_hardening.py

Tests for v0.4.0 production hardening:
  - test_request_id_present
  - test_error_handler_format
  - test_rate_limit_trigger
  - test_health_ready_db_down (mock engine)
"""
from __future__ import annotations

import asyncio
import sys
import uuid
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from clincore.core.middleware import RequestIDMiddleware
from clincore.core.error_handlers import register_error_handlers
from clincore.core.rate_limit import TenantRateLimiter, RateLimitMiddleware, reset_limiter
from clincore.core.health import router as health_router


# ── Shared event loop for the module ─────────────────────────────────────────

@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── Helper: minimal app factory ──────────────────────────────────────────────

def _base_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    register_error_handlers(app)
    return app


# ═══════════════════════════════════════════════════════════════════
# 1. REQUEST ID PRESENT
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_request_id_present_in_response():
    """Every response must carry X-Request-ID header."""
    app = _base_app()

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/ping")

    assert resp.status_code == 200
    assert "x-request-id" in resp.headers, "X-Request-ID header missing"
    rid = resp.headers["x-request-id"]
    assert len(rid) == 36, f"Expected UUID4, got: {rid!r}"


@pytest.mark.asyncio
async def test_request_id_propagated_from_client():
    """If client sends X-Request-ID it must be echoed back unchanged."""
    app = _base_app()

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    custom_id = str(uuid.uuid4())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/ping", headers={"X-Request-ID": custom_id})

    assert resp.headers["x-request-id"] == custom_id


# ═══════════════════════════════════════════════════════════════════
# 2. ERROR HANDLER FORMAT
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_error_handler_returns_json_shape_on_500():
    """Unhandled exceptions must return {error, request_id, code} — no traceback."""
    app = _base_app()

    @app.get("/boom")
    async def boom():
        raise RuntimeError("intentional crash")

    # raise_server_exceptions=False lets the ASGI error handler return 500
    # instead of re-raising the exception into the test
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/boom")

    assert resp.status_code == 500
    body = resp.json()
    assert "error" in body, f"Missing 'error' key in: {body}"
    assert "request_id" in body, f"Missing 'request_id' key in: {body}"
    assert "code" in body, f"Missing 'code' key in: {body}"
    assert body["code"] == 500
    # Stack trace must NOT be exposed
    assert "Traceback" not in body.get("error", "")
    assert "RuntimeError" not in body.get("error", "")


@pytest.mark.asyncio
async def test_error_handler_http_exception_shape():
    """FastAPI HTTPException must use the same {error, request_id, code} shape."""
    from fastapi import HTTPException

    app = _base_app()

    @app.get("/forbidden")
    async def forbidden():
        raise HTTPException(status_code=403, detail="Access denied")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/forbidden")

    assert resp.status_code == 403
    body = resp.json()
    assert body["error"] == "Access denied"
    assert body["code"] == 403
    assert "request_id" in body


@pytest.mark.asyncio
async def test_error_handler_validation_error_shape():
    """RequestValidationError must return 422 with {error, request_id, code}."""
    from pydantic import BaseModel

    app = _base_app()

    class Payload(BaseModel):
        value: int

    @app.post("/typed")
    async def typed(body: Payload):
        return body

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post("/typed", json={"value": "not-an-int"})

    assert resp.status_code == 422
    body = resp.json()
    assert "error" in body
    assert body["code"] == 422
    assert "request_id" in body


# ═══════════════════════════════════════════════════════════════════
# 3. RATE LIMIT TRIGGER
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_rate_limiter_allows_within_limit():
    """Requests within limit must all be allowed."""
    limiter = TenantRateLimiter(limit=5, window_seconds=60.0)
    tenant = "tenant-allow-test"
    for _ in range(5):
        assert await limiter.is_allowed(tenant) is True


@pytest.mark.asyncio
async def test_rate_limiter_blocks_over_limit():
    """Request exceeding limit must be rejected."""
    limiter = TenantRateLimiter(limit=3, window_seconds=60.0)
    tenant = "tenant-block-test"
    for _ in range(3):
        await limiter.is_allowed(tenant)
    # 4th request must be blocked
    assert await limiter.is_allowed(tenant) is False


@pytest.mark.asyncio
async def test_rate_limit_middleware_returns_429():
    """RateLimitMiddleware must return 429 after tenant exceeds limit."""
    reset_limiter()

    limiter = TenantRateLimiter(limit=2, window_seconds=60.0)
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(RateLimitMiddleware, limiter=limiter)
    register_error_handlers(app)

    @app.get("/resource")
    async def resource():
        return {"ok": True}

    tenant_id = f"rate-limit-{uuid.uuid4().hex[:8]}"
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        r1 = await client.get("/resource", headers={"X-Tenant-ID": tenant_id})
        r2 = await client.get("/resource", headers={"X-Tenant-ID": tenant_id})
        r3 = await client.get("/resource", headers={"X-Tenant-ID": tenant_id})

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429, f"Expected 429, got {r3.status_code}"
    body = r3.json()
    assert "error" in body
    assert body["code"] == 429


@pytest.mark.asyncio
async def test_rate_limit_does_not_affect_health_endpoints():
    """Health endpoints must bypass rate limiting even for known tenants."""
    reset_limiter()

    limiter = TenantRateLimiter(limit=1, window_seconds=60.0)
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(RateLimitMiddleware, limiter=limiter)
    app.include_router(health_router)

    tenant_id = f"health-bypass-{uuid.uuid4().hex[:8]}"
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        for _ in range(5):
            r = await client.get("/health/live", headers={"X-Tenant-ID": tenant_id})
            assert r.status_code == 200, "Health/live must not be rate-limited"


@pytest.mark.asyncio
async def test_rate_limit_independent_per_tenant():
    """Hitting the limit for tenant A must not affect tenant B."""
    limiter = TenantRateLimiter(limit=2, window_seconds=60.0)
    tenant_a = f"ta-{uuid.uuid4().hex[:8]}"
    tenant_b = f"tb-{uuid.uuid4().hex[:8]}"

    # Exhaust tenant A
    for _ in range(2):
        await limiter.is_allowed(tenant_a)
    assert await limiter.is_allowed(tenant_a) is False

    # Tenant B must still be allowed
    assert await limiter.is_allowed(tenant_b) is True


# ═══════════════════════════════════════════════════════════════════
# 4. HEALTH READY — DB DOWN (mock engine)
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_health_live_always_200():
    """/health/live must return 200 regardless of DB state."""
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    app.include_router(health_router)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/health/live")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["probe"] == "live"


@pytest.mark.asyncio
async def test_health_ready_db_up():
    """/health/ready returns 200 when DB is reachable."""
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    app.include_router(health_router)

    # Mock engine.connect to succeed
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value=None)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)

    mock_engine = MagicMock()
    mock_engine.connect = MagicMock(return_value=mock_conn)

    transport = ASGITransport(app=app)
    with patch("clincore.db.engine", mock_engine):
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get("/health/ready")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["db"] == "reachable"


@pytest.mark.asyncio
async def test_health_ready_db_down():
    """/health/ready returns 503 when DB is unreachable."""
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    app.include_router(health_router)

    # Mock engine.connect to raise
    mock_conn = AsyncMock()
    mock_conn.__aenter__ = AsyncMock(side_effect=OSError("Connection refused"))
    mock_conn.__aexit__ = AsyncMock(return_value=False)

    mock_engine = MagicMock()
    mock_engine.connect = MagicMock(return_value=mock_conn)

    transport = ASGITransport(app=app)
    with patch("clincore.db.engine", mock_engine):
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get("/health/ready")

    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "error"
    assert body["probe"] == "ready"
    assert body["db"] == "unreachable"
