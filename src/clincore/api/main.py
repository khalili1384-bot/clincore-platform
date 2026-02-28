# src/clincore/api/main.py
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from clincore.core.logging import setup_json_logging
from clincore.core.middleware import RequestIDMiddleware
from clincore.core.rate_limit import RateLimitMiddleware
from clincore.core.error_handlers import register_error_handlers
from clincore.core.health import router as health_router
from clincore.clinical.router import router as clinical_router
from clincore.pipeline.engine_wrapper import EngineError, run_engine
from clincore.mcare_engine.ui.router import router as mcare_ui_router

setup_json_logging()
log = logging.getLogger("clincore.api")

APP_VERSION = "0.2.0"
ENGINE_VERSION = "mcare_sqlite_engine_v6_1"

app = FastAPI(title="ClinCore API", version=APP_VERSION)

# ── Middleware (order: outermost first) ──────────────────────────────────────
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestIDMiddleware)

# ── Error handlers ───────────────────────────────────────────────────────────
register_error_handlers(app)

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(health_router)
app.include_router(mcare_ui_router)
app.include_router(clinical_router)

# ── Startup safeguard ────────────────────────────────────────────────────────
@app.on_event("startup")
async def _startup_safeguard():
    import sys as _sys
    from clincore.mcare_engine.ui import router as _mcare_mod
    log.info("=== STARTUP SAFEGUARD ===")
    log.info("Python: %s", _sys.version)
    log.info("MCARE router module: %s", _mcare_mod.__file__)
    _routes = [r.path for r in mcare_ui_router.routes]
    log.info("MCARE routes: %s", _routes)
    assert "/mcare/auto" in _routes, f"/mcare/auto MISSING from mcare_ui_router! Got: {_routes}"
    log.info("=== /mcare/auto CONFIRMED ===")


try:
    from clincore.api.case_engine import router as _ce_router
    app.include_router(_ce_router)
except Exception as _e:
    log.warning("case_engine skipped: %s", _e)

try:
    from clincore.api.bootstrap import router as _bootstrap_router
    app.include_router(_bootstrap_router)
except Exception as _e:
    log.warning("bootstrap skipped: %s", _e)

try:
    from clincore.api.auth_api_keys import router as _auth_router
    app.include_router(_auth_router)
except Exception as _e:
    log.warning("auth_api_keys skipped: %s", _e)

try:
    from clincore.api.admin import router as _admin_router
    app.include_router(_admin_router)
except Exception as _e:
    log.warning("admin skipped: %s", _e)

try:
    from clincore.api.feedback_router import router as _feedback_router
    app.include_router(_feedback_router)
except Exception as _e:
    log.warning("feedback_router skipped: %s", _e)


# ── Legacy /health (backwards compat) ────────────────────────────────────────
@app.get("/health")
async def health_legacy():
    return {"status": "ok"}


# ── Version ───────────────────────────────────────────────────────────────────
@app.get("/version")
async def version():
    return {"api_version": APP_VERSION, "engine_version": ENGINE_VERSION}


# ── EngineError handler (domain-specific, kept alongside engine) ─────────────
@app.exception_handler(EngineError)
async def engine_error_handler(request: Request, exc: EngineError) -> JSONResponse:
    code = getattr(exc, "code", "ENGINE_CRASH")
    return JSONResponse(
        status_code=400,
        content={
            "error": str(exc),
            "request_id": getattr(request.state, "request_id", None),
            "code": 400,
            "engine_code": code,
        },
    )


# ── Score endpoint ────────────────────────────────────────────────────────────
class ScoreRequest(BaseModel):
    symptom_ids: List[int] = Field(..., min_length=1)
    top_n: int = Field(5, ge=1, le=50)


class ScoreResponse(BaseModel):
    results: List[Dict[str, Any]]
    request_id: Optional[str] = None
    case_type_used: Optional[str] = None


@app.post("/score", response_model=ScoreResponse)
async def score(req: ScoreRequest, request: Request):
    results = run_engine(req.symptom_ids, top_n=req.top_n)
    return {
        "results": results,
        "request_id": getattr(request.state, "request_id", None),
        "case_type_used": None,
    }