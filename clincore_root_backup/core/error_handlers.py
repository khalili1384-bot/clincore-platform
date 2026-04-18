"""
src/clincore/core/error_handlers.py

Unified exception handlers for ClinCore FastAPI app.

All errors return:
    {
        "error": "<short message>",
        "request_id": "<uuid | null>",
        "code": <http_status_int>
    }

Stack traces are NEVER exposed in the response body.
They are logged server-side (ERROR level) for ERROR+ cases.
"""
from __future__ import annotations

import logging
import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

_log = logging.getLogger("clincore.errors")

_PRODUCTION = os.getenv("APP_ENV", "development").lower() in {"production", "prod"}


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _err_body(message: str, code: int, request: Request) -> dict:
    return {
        "error": message,
        "request_id": _request_id(request),
        "code": code,
    }


def register_error_handlers(app: FastAPI) -> None:
    """Attach all unified error handlers to the given FastAPI app."""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = str(exc.detail) if exc.detail else "Request error"
        if exc.status_code >= 500:
            _log.error(
                "HTTP %d %s request_id=%s path=%s",
                exc.status_code,
                detail,
                _request_id(request),
                request.url.path,
            )
        return JSONResponse(
            status_code=exc.status_code,
            content=_err_body(detail, exc.status_code, request),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        _log.warning(
            "Validation error request_id=%s path=%s",
            _request_id(request),
            request.url.path,
        )
        body = _err_body("Invalid request body or parameters", 422, request)
        if not _PRODUCTION:
            body["detail"] = exc.errors()
        return JSONResponse(status_code=422, content=body)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        _log.exception(
            "Unhandled exception request_id=%s path=%s",
            _request_id(request),
            request.url.path,
        )
        return JSONResponse(
            status_code=500,
            content=_err_body("Unexpected server error", 500, request),
        )
