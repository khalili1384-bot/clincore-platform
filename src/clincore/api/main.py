# src/clincore/api/main.py
from __future__ import annotations

import time
import uuid
import logging
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from clincore.api.logging_conf import setup_logging
from clincore.clinical.router import router as clinical_router
from clincore.pipeline.engine_wrapper import EngineError, run_engine
from clincore.mcare_engine.ui.router import router as mcare_ui_router

setup_logging()
log = logging.getLogger("clincore.api")

APP_VERSION = "0.1.0"
ENGINE_VERSION = "mcare_sqlite_engine_v6_1"

app = FastAPI(title="ClinCore API", version=APP_VERSION)

app.include_router(mcare_ui_router)
app.include_router(clinical_router)

try:
    from clincore.api.case_engine import router as _ce_router
    app.include_router(_ce_router)
except Exception as _e:
    import logging as _lg
    _lg.getLogger("clincore.api").warning("case_engine skipped: %s", _e)

try:
    from clincore.api.bootstrap import router as _bootstrap_router
    app.include_router(_bootstrap_router)
except Exception as _e:
    import logging as _lg
    _lg.getLogger("clincore.api").warning("bootstrap skipped: %s", _e)

try:
    from clincore.api.auth_api_keys import router as _auth_router
    app.include_router(_auth_router)
except Exception as _e:
    import logging as _lg
    _lg.getLogger("clincore.api").warning("auth_api_keys skipped: %s", _e)


# -----------------------------
# Middleware: request_id + logging
# -----------------------------
@app.middleware("http")
async def request_context_logger(request: Request, call_next):
    start = time.perf_counter()

    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id

    try:
        response = await call_next(request)
    finally:
        ms = (time.perf_counter() - start) * 1000.0
        # لاگ خلاصه
        status_code = getattr(locals().get("response", None), "status_code", 500)
        log.info(
            "request_id=%s method=%s path=%s status=%s ms=%.2f",
            request_id,
            request.method,
            request.url.path,
            status_code,
            ms,
        )

    response.headers["X-Request-ID"] = request_id
    return response


# -----------------------------
# Unified error handling
# -----------------------------
@app.exception_handler(EngineError)
async def engine_error_handler(request: Request, exc: EngineError):
    # EngineError شما: code + message (یا str(exc))
    code = getattr(exc, "code", "ENGINE_CRASH")
    msg = str(exc)
    return JSONResponse(
        status_code=400,
        content={
            "error": {"code": code, "message": msg},
            "request_id": getattr(request.state, "request_id", None),
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    # برای اینکه کلاینت همیشه یک فرم ثابت ببیند
    return JSONResponse(
        status_code=422,
        content={
            "error": {"code": "VALIDATION_ERROR", "message": "Invalid input data"},
            "details": exc.errors(),
            "request_id": getattr(request.state, "request_id", None),
        },
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    log.exception("Unhandled error request_id=%s", getattr(request.state, "request_id", None))
    return JSONResponse(
        status_code=500,
        content={
            "error": {"code": "INTERNAL_ERROR", "message": "Unexpected server error"},
            "request_id": getattr(request.state, "request_id", None),
        },
    )


# -----------------------------
# Health & Version
# -----------------------------
@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/version")
async def version():
    return {"api_version": APP_VERSION, "engine_version": ENGINE_VERSION}


# -----------------------------
# API models (ساده، بدون فایل جدا)
# -----------------------------
from pydantic import BaseModel, Field


class ScoreRequest(BaseModel):
    symptom_ids: List[int] = Field(..., min_length=1)
    top_n: int = Field(5, ge=1, le=50)


class ScoreResponse(BaseModel):
    results: List[Dict[str, Any]]
    request_id: Optional[str] = None
    case_type_used: Optional[str] = None


# -----------------------------
# Main endpoint
# -----------------------------
@app.post("/score", response_model=ScoreResponse)
async def score(req: ScoreRequest, request: Request):
    results = run_engine(req.symptom_ids, top_n=req.top_n)
    return {
        "results": results,
        "request_id": getattr(request.state, "request_id", None),
        "case_type_used": None,
    }