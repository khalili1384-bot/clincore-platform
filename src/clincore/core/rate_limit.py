"""
src/clincore/core/rate_limit.py

Tenant-level in-memory sliding-window rate limiter.

Defaults: 60 requests per 60-second window per tenant.
Returns HTTP 429 when exceeded.

Design:
- asyncio.Lock per tenant bucket (no global lock contention)
- deque of timestamps, O(1) amortised per call
- No external dependencies (pure stdlib + asyncio)
- Does NOT affect unauthenticated endpoints (health, /score, etc.)
- Does NOT touch RLS or DB schema
"""
from __future__ import annotations

import asyncio
import time
from collections import deque
from collections.abc import Callable, Awaitable
from typing import Any

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

__all__ = [
    "TenantRateLimiter",
    "RateLimitMiddleware",
]


class TenantRateLimiter:
    """
    Sliding-window rate limiter keyed on an arbitrary string (tenant_id).

    Thread/async-safe: one asyncio.Lock per bucket.
    Old buckets are never cleaned up by default (tenants are long-lived).
    If you need GC, call `evict_inactive()` periodically.
    """

    def __init__(self, limit: int = 60, window_seconds: float = 60.0) -> None:
        self.limit = limit
        self.window = window_seconds
        self._buckets: dict[str, deque[float]] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._meta_lock = asyncio.Lock()

    async def _get_bucket(self, key: str) -> tuple[deque[float], asyncio.Lock]:
        async with self._meta_lock:
            if key not in self._buckets:
                self._buckets[key] = deque()
                self._locks[key] = asyncio.Lock()
            return self._buckets[key], self._locks[key]

    async def is_allowed(self, key: str) -> bool:
        """Return True if the request is within quota, False if rate-limited."""
        bucket, lock = await self._get_bucket(key)
        now = time.monotonic()
        cutoff = now - self.window

        async with lock:
            # evict timestamps outside the window
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= self.limit:
                return False

            bucket.append(now)
            return True

    async def evict_inactive(self, idle_seconds: float = 300.0) -> int:
        """Remove buckets whose last request was more than idle_seconds ago."""
        now = time.monotonic()
        cutoff = now - idle_seconds
        async with self._meta_lock:
            stale = [
                k for k, dq in self._buckets.items()
                if not dq or dq[-1] <= cutoff
            ]
            for k in stale:
                del self._buckets[k]
                del self._locks[k]
        return len(stale)


# ── Global singleton (app-level) ─────────────────────────────────────────────
_default_limiter: TenantRateLimiter | None = None


def get_limiter() -> TenantRateLimiter:
    global _default_limiter
    if _default_limiter is None:
        import os
        limit = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
        _default_limiter = TenantRateLimiter(limit=limit, window_seconds=60.0)
    return _default_limiter


def reset_limiter() -> None:
    """Reset singleton — used in tests only."""
    global _default_limiter
    _default_limiter = None


# ── FastAPI dependency (for authenticated endpoints) ─────────────────────────

async def check_rate_limit(request: Request) -> None:
    """
    FastAPI dependency to enforce rate limiting on authenticated endpoints.

    Reads tenant_id from request.state (set by auth dependency).
    Skips limit check if no tenant_id present (unauthenticated endpoints).
    """
    tenant_id: str = getattr(request.state, "tenant_id", "") or ""
    if not tenant_id:
        return

    limiter = get_limiter()
    allowed = await limiter.is_allowed(tenant_id)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Max 60 requests per minute per tenant.",
        )


# ── Middleware (alternative: applies to all authenticated routes via header) ──

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware that rate-limits requests carrying X-Tenant-ID header.

    Only enforces limits when a tenant is identifiable from request state
    (populated by auth dependency) or X-Tenant-ID header.
    Skips unauthenticated paths entirely.
    """

    _SKIP_PATHS = frozenset({
        "/health", "/health/live", "/health/ready",
        "/version", "/score", "/docs", "/openapi.json", "/redoc",
    })

    def __init__(self, app: Any, limiter: TenantRateLimiter | None = None) -> None:
        super().__init__(app)
        self._limiter = limiter or get_limiter()

    async def dispatch(self, request: Request, call_next: Callable[..., Awaitable[Response]]) -> Response:
        path = request.url.path

        if path in self._SKIP_PATHS or path.startswith("/mcare"):
            return await call_next(request)

        tenant_id = (
            getattr(request.state, "tenant_id", "")
            or request.headers.get("X-Tenant-ID", "")
        )

        if tenant_id:
            allowed = await self._limiter.is_allowed(tenant_id)
            if not allowed:
                from starlette.responses import JSONResponse as _JSONResponse
                rid = getattr(request.state, "request_id", None)
                return _JSONResponse(
                    status_code=429,
                    content={
                        "error": "Rate limit exceeded. Max 60 requests per minute per tenant.",
                        "request_id": rid,
                        "code": 429,
                    },
                )

        return await call_next(request)
