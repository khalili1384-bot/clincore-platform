# ───────────────────────────────────────────────────────
# ClinCore Platform — Proprietary & Confidential
# Copyright © 2026 ClinCore
# All rights reserved. Unauthorized use strictly prohibited.
# ───────────────────────────────────────────────────────
from datetime import datetime, timezone
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Limits per UTC day per tenant
# /mcare/auto 100   /clinical-cases 200   default 1000
LIMITS: dict[str, int] = {
    "/mcare/auto": 100,
    "/clinical-cases": 200,
}
DEFAULT_LIMIT = 1_000
_counters: dict[str, int] = {}  # TODO Phase15-prod: move to PostgreSQL


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Tenant-scoped UTC-day rate limiter. Returns 429 when limit exceeded."""

    async def dispatch(self, request: Request, call_next):
        tenant_id = (
            getattr(request.state, "tenant_id", None)
            or request.headers.get("X-Tenant-Id", "anonymous").strip()
        )
        path = request.url.path
        limit = LIMITS.get(path, DEFAULT_LIMIT)
        key = f"{tenant_id}:{path}:{_today_utc()}"
        _counters[key] = _counters.get(key, 0) + 1
        if _counters[key] > limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "rate limit exceeded"},
            )
        return await call_next(request)
