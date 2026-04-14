# ───────────────────────────────────────────────────────
# ClinCore Platform — Proprietary & Confidential
# Copyright © 2026 ClinCore
# All rights reserved. Unauthorized use strictly prohibited.
# ───────────────────────────────────────────────────────
import os
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import psycopg

# Limits per UTC day per tenant
# /mcare/auto 100   /clinical-cases 200   default 1000
LIMITS: dict[str, int] = {
    "/mcare/auto": 100,
    "/clinical-cases": 200,
}
DEFAULT_LIMIT = 1_000

# PostgreSQL connection string
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # fallback: build from individual env vars (no password in source code)
    _host = os.getenv("DB_HOST", "127.0.0.1")
    _port = os.getenv("DB_PORT", "5432")
    _user = os.getenv("DB_USER", "clincore_user")
    _pass = os.getenv("DB_PASSWORD", "")
    _name = os.getenv("DB_NAME", "clincore")
    DATABASE_URL = f"postgresql://{_user}:{_pass}@{_host}:{_port}/{_name}"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Tenant-scoped UTC-day rate limiter with PostgreSQL counter. Returns 429 when limit exceeded."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        
        # Skip rate limiting for super-admin, auth, and shop endpoints
        if path.startswith("/super-admin") or path.startswith("/auth") or path.startswith("/shop"):
            return await call_next(request)
        
        tenant_id = (
            getattr(request.state, "tenant_id", None)
            or request.headers.get("X-Tenant-Id", "anonymous").strip()
        )
        limit = LIMITS.get(path, DEFAULT_LIMIT)
        
        # Connect to PostgreSQL and check rate limit
        try:
            async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
                async with conn.cursor() as cur:
                    # Count requests for this tenant/endpoint today (UTC)
                    count_query = f"""
                        SELECT COUNT(*) FROM usage_events
                        WHERE tenant_id = '{tenant_id}'
                        AND endpoint_path = '{path}'
                        AND created_at >= date_trunc('day', now() AT TIME ZONE 'UTC')
                    """
                    await cur.execute(count_query)
                    result = await cur.fetchone()
                    count = result[0] if result else 0
                    
                    # Check if limit exceeded
                    if count >= limit:
                        return JSONResponse(
                            status_code=429,
                            content={"detail": "rate limit exceeded"},
                        )
                    
                    # Insert usage event
                    insert_query = f"""
                        INSERT INTO usage_events (tenant_id, event_type, endpoint_path, status_code, created_at)
                        VALUES ('{tenant_id}', 'api_request', '{path}', 200, now())
                    """
                    await cur.execute(insert_query)
                    await conn.commit()
        except Exception as e:
            # If DB fails, log and allow request (fail-open for rate limiting)
            print(f"Rate limit DB error: {e}")
        
        return await call_next(request)
