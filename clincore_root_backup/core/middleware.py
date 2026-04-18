"""
src/clincore/core/middleware.py

Request ID middleware for ClinCore FastAPI app.

- Generates UUID4 per request (or reuses client-provided X-Request-ID)
- Stores in request_id_ctx ContextVar
- Adds X-Request-ID to every response header
- Emits structured access log: method, path, status, duration_ms
"""
from __future__ import annotations

import time
import uuid
import logging
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from clincore.core.logging import request_id_ctx, tenant_id_ctx

_log = logging.getLogger("clincore.access")

# Headers we NEVER log values of (guard against key leakage)
_REDACTED_HEADERS = frozenset({"x-api-key", "authorization"})


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Assign a unique request_id to every incoming HTTP request."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        raw_id = request.headers.get("X-Request-ID", "").strip()
        request_id = raw_id if raw_id else str(uuid.uuid4())

        token_rid = request_id_ctx.set(request_id)
        token_tid = tenant_id_ctx.set("")

        request.state.request_id = request_id

        start = time.perf_counter()
        try:
            response: Response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000.0
            _log.error(
                "unhandled exception in middleware",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round(duration_ms, 2),
                },
            )
            raise
        finally:
            request_id_ctx.reset(token_rid)
            tenant_id_ctx.reset(token_tid)

        duration_ms = (time.perf_counter() - start) * 1000.0

        response.headers["X-Request-ID"] = request_id

        _log.info(
            "%s %s %d %.2fms",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            extra={
                "request_id": request_id,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
            },
        )

        return response
