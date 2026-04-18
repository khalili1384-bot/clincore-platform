"""
src/clincore/core/health.py

Health + readiness probe endpoints.

GET /health/live  — liveness: always 200 (process is alive)
GET /health/ready — readiness: checks DB connectivity with SELECT 1
                    returns 503 if DB unreachable within timeout
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

import clincore.db as _db_module

_log = logging.getLogger("clincore.health")

router = APIRouter(tags=["health"])

_DB_PING_TIMEOUT = 3.0  # seconds


@router.get("/health/live")
async def health_live() -> JSONResponse:
    """Liveness probe — always returns 200 if the process is running."""
    return JSONResponse(status_code=200, content={"status": "ok", "probe": "live"})


@router.get("/health/ready")
async def health_ready() -> JSONResponse:
    """
    Readiness probe — returns 200 only when the DB is reachable.

    Opens an async session, executes SELECT 1, and returns within timeout.
    Returns 503 if DB is down or times out.
    """
    engine = _db_module.engine

    try:
        async with asyncio.timeout(_DB_PING_TIMEOUT):
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        return JSONResponse(
            status_code=200,
            content={"status": "ok", "probe": "ready", "db": "reachable"},
        )
    except TimeoutError:
        _log.error("health_ready: DB ping timed out after %.1fs", _DB_PING_TIMEOUT)
        return JSONResponse(
            status_code=503,
            content={"status": "error", "probe": "ready", "db": "timeout"},
        )
    except Exception as exc:
        _log.error("health_ready: DB unreachable — %s", exc)
        return JSONResponse(
            status_code=503,
            content={"status": "error", "probe": "ready", "db": "unreachable"},
        )
