# ───────────────────────────────────────────────────────
# ClinCore Platform — Proprietary & Confidential
# Copyright © 2026 ClinCore
# All rights reserved. Unauthorized use strictly prohibited.
# ───────────────────────────────────────────────────────
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

SKIP_PATHS = {"/health", "/version", "/docs", "/openapi.json", "/redoc", "/favicon.ico"}


class RLSMiddleware(BaseHTTPMiddleware):
    """Fail-closed tenant guard: X-Tenant-Id missing or empty returns 400."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path in SKIP_PATHS:
            return await call_next(request)
        tenant_id = request.headers.get("X-Tenant-Id", "").strip()
        if not tenant_id:
            return JSONResponse(
                status_code=400,
                content={"detail": "X-Tenant-Id header is required"},
            )
        request.state.tenant_id = tenant_id
        return await call_next(request)
