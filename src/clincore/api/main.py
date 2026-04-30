"""
FastAPI entrypoint for ClinCore platform.
Minimal, safe, fail-closed design.
"""
import asyncio
import logging
import sys
import os
from contextlib import asynccontextmanager

# Windows event loop fix - MUST be before any async imports
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown."""
    # Startup
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
    
    yield
    
    # Shutdown
    logger.info("🛑 ClinCore API shutting down...")

app = FastAPI(
    title="ClinCore API",
    version="0.2.0",
    description="Clinical AI platform with tenant isolation and RLS",
    lifespan=lifespan,
)

# Mount static files
import pathlib as _pathlib
app.mount(
    "/static",
    StaticFiles(directory=str(_pathlib.Path(__file__).resolve().parent.parent / "static")),
    name="static",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "null",
        "*"
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Optional core middleware (if available)
try:
    from clincore.core.middleware import RequestIDMiddleware
    from clincore.core.errorhandlers import register_error_handlers
    
    app.add_middleware(RequestIDMiddleware)
    register_error_handlers(app)
    logger.info("✅ Core middleware integrated")
except ImportError as e:
    logger.warning("⚠️ Core middleware skipped: %s", e)

# Rate limit middleware (pure ASGI to avoid BaseHTTPMiddleware issues)
from clincore.core.rate_limit import check_and_increment
from clincore.core.db import AsyncSessionLocal
from sqlalchemy import text

class RateLimitMiddleware:
    """Rate limiting middleware using PostgreSQL counters (pure ASGI)."""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        from starlette.requests import Request
        from starlette.responses import JSONResponse
        
        request = Request(scope, receive)
        path = request.url.path
        
        # Skip rate limiting for static files, docs, health checks
        if path.startswith("/static") or path.startswith("/panel") or path in ("/health", "/version", "/docs", "/redoc", "/openapi.json"):
            await self.app(scope, receive, send)
            return
        
        # Skip for super-admin and auth endpoints
        if path.startswith("/super-admin") or path.startswith("/auth") or path.startswith("/shop") or path.startswith("/store"):
            await self.app(scope, receive, send)
            return
        
        # Get tenant_id from header
        tenant_id = request.headers.get("X-Tenant-Id", "").strip()
        
        # Skip if no tenant_id (will be caught by TenantMiddleware)
        if not tenant_id:
            await self.app(scope, receive, send)
            return
        
        # Check and increment rate limit
        try:
            async with AsyncSessionLocal() as session:
                allowed, current, limit = await check_and_increment(session, tenant_id, path)
                await session.commit()
                
                if not allowed:
                    response = JSONResponse(
                        status_code=429,
                        content={"detail": "rate limit exceeded"}
                    )
                    await response(scope, receive, send)
                    return
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            # Fail open - allow request if rate limit check fails
        
        # Process request
        await self.app(scope, receive, send)

app.add_middleware(RateLimitMiddleware)

# Tenant validation middleware (class-based to run before route matching)
class TenantMiddleware:
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        from starlette.requests import Request
        request = Request(scope, receive)
        path = request.url.path
        method = request.method
        
        # Skip tenant validation for static files
        if path.startswith("/static") or path.startswith("/panel"):
            await self.app(scope, receive, send)
            return
        
        # Skip tenant validation for OPTIONS requests (CORS preflight)
        if method == "OPTIONS":
            await self.app(scope, receive, send)
            return
        
        # Always set tenant_id from header if present
        tenant_id = request.headers.get("X-Tenant-Id")
        if tenant_id:
            # Set tenant_id in scope state so it's available in request.state
            scope["state"] = scope.get("state", {})
            scope["state"]["tenant_id"] = tenant_id
        
        # Skip tenant requirement check for health/version/test/docs/openapi/super-admin/auth/shop/store/patients/encounters/cases/appointments
        if path in ("/health", "/version", "/test", "/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"):
            await self.app(scope, receive, send)
            return
        if path.startswith("/super-admin") or path.startswith("/auth") or path.startswith("/shop") or path.startswith("/store") or path.startswith("/patients") or path.startswith("/encounters") or path.startswith("/clinical-cases") or path.startswith("/appointments"):
            await self.app(scope, receive, send)
            return
        
        # Require tenant_id for other paths
        if tenant_id is None:
            from fastapi.responses import JSONResponse
            response = JSONResponse(status_code=400, content={"error": "X-Tenant-Id is required"})
            await response(scope, receive, send)
            return
        
        await self.app(scope, receive, send)

app.add_middleware(TenantMiddleware)

# API key auth middleware (temporarily disabled for debugging)
# @app.middleware("http")
# async def api_key_middleware(request: Request, call_next):
#     # Skip auth for health/docs/openapi/super-admin/auth/shop/store/patients/encounters/cases/appointments
#     if request.url.path in ("/health", "/version", "/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"):
#         return await call_next(request)
#     if request.url.path.startswith("/super-admin") or request.url.path.startswith("/auth") or request.url.path.startswith("/shop") or request.url.path.startswith("/store") or request.url.path.startswith("/patients") or request.url.path.startswith("/encounters") or request.url.path.startswith("/clinical-cases") or request.url.path.startswith("/appointments"):
#         return await call_next(request)
# 
#     raw_auth = request.headers.get("Authorization")
#     if raw_auth is None or not raw_auth.startswith("Bearer "):
#         return JSONResponse(status_code=401, content={"error": "Authorization: Bearer <api_key> required"})
# 
#     raw_key = raw_auth.removeprefix("Bearer ").strip()
#     key_hash = __import__("hashlib").sha256(raw_key.encode()).hexdigest()
#     tenant_id = request.headers.get("X-Tenant-Id", "").strip()
# 
#     import os, psycopg
#     _db = os.getenv("DATABASE_URL") or (
#         f"postgresql://{os.getenv('DB_USER','clincore_user')}:"
#         f"{os.getenv('DB_PASSWORD','')}@"
#         f"{os.getenv('DB_HOST','127.0.0.1')}:"
#         f"{os.getenv('DB_PORT','5432')}/"
#         f"{os.getenv('DB_NAME','clincore')}"
#     )
#     try:
#         async with await psycopg.AsyncConnection.connect(_db) as conn:
#             async with conn.cursor() as cur:
#                 await cur.execute(
#                     f"SELECT tenant_id FROM api_keys WHERE key_hash = '{key_hash}' AND is_active = true LIMIT 1"
#                 )
#                 row = await cur.fetchone()
#     except Exception as e:
#         logger.error("api_key_middleware DB error: %s", e)
#         return JSONResponse(status_code=503, content={"error": "auth service unavailable"})
# 
#     if row is None:
#         return JSONResponse(status_code=401, content={"error": "invalid or inactive api key"})
# 
#     db_tenant_id = str(row[0])
#     if tenant_id and db_tenant_id != tenant_id:
#         return JSONResponse(status_code=403, content={"error": "api key does not belong to this tenant"})
# 
#     request.state.api_key = raw_key
#     request.state.validated_tenant_id = db_tenant_id
#     return await call_next(request)


# Core health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/version")
async def version():
    """Version endpoint."""
    return {"version": "0.2.0"}


@app.get("/test")
async def test():
    """Test endpoint to check if app routing works."""
    return {"test": "ok"}


# ── Routers (module scope) ──────────────────────────────────────────────────

# MCARE engine (critical - no prefix, routes already have /mcare)
try:
    from clincore.mcare_engine.ui.router import router as mcare_router
    app.include_router(mcare_router)
    logger.info("✅ MCARE integrated")
except ImportError as e:
    logger.warning("⚠️ MCARE skipped: %s", e)

# Patients router (optional)
try:
    from clincore.api.patients import router as patients_router
    app.include_router(patients_router)
    logger.info("✅ Patients integrated")
except Exception as e:
    import traceback; traceback.print_exc()
    logger.warning("⚠️ Patients skipped: %s", e)

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
    app.include_router(auth_router)
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

# Shop Product router (public read, admin write)
try:
    from clincore.clinical.shop_product_router import router as shop_product_router
    from clincore.shop.orders_router import router as shop_orders_router
    from clincore.shop.shop_router import router as shop_pages_router
    app.include_router(shop_product_router)
    app.include_router(shop_orders_router)
    app.include_router(shop_pages_router)
    logger.info("✅ Shop integrated")
except ImportError as e:
    logger.warning("⚠️ Shop skipped: %s", e)

# Super Admin API router (general tenant/api-key management)
try:
    from clincore.api.super_admin import router as super_admin_api_router
    app.include_router(super_admin_api_router)
    logger.info("✅ Super Admin API integrated")
except ImportError as e:
    logger.warning("⚠️ Super Admin API skipped: %s", e)

# Encounters router (optional)
try:
    from clincore.api.encounters import router as encounters_router
    app.include_router(encounters_router)
    logger.info("✅ Encounters integrated")
except ImportError as e:
    logger.warning("⚠️ Encounters skipped: %s", e)

# Clinical Cases router (optional)
try:
    from clincore.api.cases import router as cases_router
    app.include_router(cases_router)
    logger.info("✅ Clinical Cases integrated")
except ImportError as e:
    logger.warning("⚠️ Clinical Cases skipped: %s", e)

# Appointments router (optional)
try:
    from clincore.api.appointments import router as appointments_router
    app.include_router(appointments_router)
    logger.info("✅ Appointments integrated")
except ImportError as e:
    logger.warning("⚠️ Appointments skipped: %s", e)

# Panel router (optional)
try:
    from clincore.ui.panel_router import router as panel_router
    app.include_router(panel_router)
    logger.info("✅ Panel integrated")
except ImportError as e:
    logger.warning("⚠️ Panel skipped: %s", e)


# ── Startup/Shutdown ────────────────────────────────────────────────────────
# (Moved to lifespan handler above)

# Shop frontend
_frontend = r'D:\clincore-platform\frontend'
if os.path.isdir(_frontend):
    app.mount('/store', StaticFiles(directory=_frontend, html=True), name='shop')


