"""
src/clincore/core/logging.py

JSON structured logging + request_id contextvar for ClinCore.

Usage:
    from clincore.core.logging import setup_json_logging, request_id_ctx, tenant_id_ctx

    setup_json_logging()  # call once at app startup

    request_id_ctx.set("some-uuid")
    tenant_id_ctx.set("tenant-uuid")
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from contextvars import ContextVar
from typing import Any

__all__ = [
    "request_id_ctx",
    "tenant_id_ctx",
    "setup_json_logging",
]

# ── Context variables shared across the request lifecycle ────────────────────
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")
tenant_id_ctx: ContextVar[str] = ContextVar("tenant_id", default="")


# ── JSON log formatter ────────────────────────────────────────────────────────

class _JsonFormatter(logging.Formatter):
    """Emit one JSON object per log record.

    Fields always present:
        timestamp  ISO-8601 UTC
        level      DEBUG / INFO / WARNING / ERROR / CRITICAL
        logger     logger name
        message    formatted log message

    Fields injected from context (empty string when absent):
        request_id
        tenant_id

    For ERROR+ records the ``exc`` field is added (type + str only, NO traceback
    in production to avoid leaking internals).
    """

    _PROD_LEVELS = {"production", "prod"}

    def __init__(self) -> None:
        super().__init__()
        self._production = os.getenv("APP_ENV", "development").lower() in self._PROD_LEVELS

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self._utc_iso(record.created),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_ctx.get(""),
            "tenant_id": tenant_id_ctx.get(""),
        }

        if record.exc_info:
            exc_type, exc_val, _ = record.exc_info
            payload["exc"] = {
                "type": exc_type.__name__ if exc_type else "Unknown",
                "detail": str(exc_val),
            }

        return json.dumps(payload, ensure_ascii=False, default=str)

    @staticmethod
    def _utc_iso(created: float) -> str:
        t = time.gmtime(created)
        ms = int((created % 1) * 1000)
        return (
            f"{t.tm_year:04d}-{t.tm_mon:02d}-{t.tm_mday:02d}"
            f"T{t.tm_hour:02d}:{t.tm_min:02d}:{t.tm_sec:02d}.{ms:03d}Z"
        )


# ── Public setup ─────────────────────────────────────────────────────────────

def setup_json_logging(level: str | None = None) -> None:
    """Configure root logger with JSON formatter.

    Safe to call multiple times — won't add duplicate handlers.
    """
    root = logging.getLogger()

    if any(isinstance(h, logging.StreamHandler) and isinstance(h.formatter, _JsonFormatter)
           for h in root.handlers):
        return

    effective_level = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    root.setLevel(effective_level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    root.addHandler(handler)
