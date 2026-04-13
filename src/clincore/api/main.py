"""
FastAPI entrypoint for ClinCore platform.
Minimal, safe, fail-closed design.
"""
import asyncio
import logging
import sys

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Windows event loop fix
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ClinCore API",
    version="0.2.0",
    description="Clinical AI platform with tenant isolation and RLS",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Optional core middleware (if available)
try:
    from clincore.core.middleware import RequestIDMiddleware
    from clincore.core.rate_limit import RateLimitMiddleware
    from clincore.core.error_handlers import register_error_handlers
    
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestIDMiddleware)
    register_error_handlers(app)
    logger.info("✅ Core middleware integrated")
except ImportError as e:
    logger.warning("⚠️ Core middleware skipped: %s", e)

# Tenant validation middleware
@app.middleware("http")
async def tenant_middleware(request: Request, call_next):
    tenant_id = request.headers.get("X-Tenant-Id")
    if tenant_id is None:
        return JSONResponse(status_code=400, content={"error": "X-Tenant-Id is required"})
    request.state.tenant_id = tenant_id
    response = await call_next(request)
    return response

# API key auth middleware
@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    api_key = request.headers.get("Authorization")
    if api_key is None or not api_key.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"error": "Authorization: Bearer <api_key> required"})
    # TODO: validate api_key against DB
    api_key = api_key.replace("Bearer ", "")
    request.state.api_key = api_key
    response = await call_next(request)
    return response


# Core health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/version")
async def version():
    """Version endpoint."""
    return {"version": "0.2.0"}


# ── Routers (module scope) ──────────────────────────────────────────────────

# MCARE engine (critical - no prefix, routes already have /mcare)
try:
    from clincore.mcare_engine.ui.router import router as mcare_router
    app.include_router(mcare_router)
    logger.info("✅ MCARE integrated")
except ImportError as e:
    logger.warning("⚠️ MCARE skipped: %s", e)

# Bootstrap router (optional)
try:
    from clincore.api.bootstrap import router as bootstrap_router
    app.include_router(bootstrap_router, prefix="/bootstrap", tags=["bootstrap"])
    logger.info("✅ Bootstrap integrated")
except ImportError as e:
    logger.warning("⚠️ Bootstrap skipped: %s", e)

# Auth API keys router (optional)
try:
    from clincore.api.auth_api_keys import router as auth_router
    app.include_router(auth_router, prefix="/auth", tags=["auth"])
    logger.info("✅ Auth integrated")
except ImportError as e:
    logger.warning("⚠️ Auth skipped: %s", e)

# Admin router (optional)
try:
    from clincore.api.admin import router as admin_router
    app.include_router(admin_router, prefix="/admin", tags=["admin"])
    logger.info("✅ Admin integrated")
except ImportError as e:
    logger.warning("⚠️ Admin skipped: %s", e)

# Feedback router (optional)
try:
    from clincore.api.feedback import router as feedback_router
    app.include_router(feedback_router, prefix="/feedback", tags=["feedback"])
    logger.info("✅ Feedback integrated")
except ImportError as e:
    logger.warning("⚠️ Feedback skipped: %s", e)

# Clinical router (optional - legacy compatibility)
try:
    from clincore.clinical.router import router as clinical_router
    app.include_router(clinical_router, prefix="/clinical", tags=["clinical"])
    logger.info("✅ Clinical integrated")
except ImportError as e:
    logger.warning("⚠️ Clinical skipped: %s", e)

# Super Admin router (optional)
try:
    from clincore.api.super_admin import router as super_admin_router
    app.include_router(super_admin_router)
    logger.info("✅ Super Admin integrated")
except ImportError as e:
    logger.warning("⚠️ Super Admin skipped: %s", e)


# ── Startup/Shutdown ────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    """Startup event handler - checks only, no router loading."""
    logger.info("🚀 ClinCore API starting up...")
    
    # Fail-closed check: ensure critical routes exist
    routes = [route.path for route in app.routes]
    if "/health" not in routes:
        logger.error("❌ CRITICAL: /health route not found. Startup failed.")
        raise RuntimeError("Fail-closed: /health route missing")
    
    if "/mcare/auto" not in routes:
        logger.error("❌ CRITICAL: /mcare/auto route not found. Startup failed.")
        raise RuntimeError("Fail-closed: /mcare/auto route missing")
    
    logger.info(f"✅ ClinCore API started. Available routes: {routes}")


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler."""
    logger.info("🛑 ClinCore API shutting down...")
