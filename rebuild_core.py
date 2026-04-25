"""
rebuild_core.py  ClinCore Core Recovery Script
Run from D:/clincore-platform:
    python rebuild_core.py
Writes 4 missing core files. MCARE / synthesis.db / alembic untouched.
"""
import sys
from pathlib import Path

HERE = Path(__file__).parent.resolve()
CORE_DIR = HERE / "src" / "clincore" / "core"

PROTECTED = {
    "mcare_sqlite_engine_v6_1.py",
    "mcare_config_v6_1.json",
    "clinical_extractor.py",
    "synthesis.db",
}

LIC = (
    "# " + chr(0x2500)*55 + "\n"
    "# ClinCore Platform — Proprietary & Confidential\n"
    "# Copyright © 2026 ClinCore\n"
    "# All rights reserved. Unauthorized use strictly prohibited.\n"
    "# " + chr(0x2500)*55 + "\n"
)

FILES = {}

FILES['rls.py'] = LIC + 'from fastapi import Request\nfrom fastapi.responses import JSONResponse\nfrom starlette.middleware.base import BaseHTTPMiddleware\n\nSKIP_PATHS = {"/health", "/version", "/docs", "/openapi.json", "/redoc", "/favicon.ico"}\n\n\nclass RLSMiddleware(BaseHTTPMiddleware):\n    """Fail-closed tenant guard: X-Tenant-Id missing or empty returns 400."""\n\n    async def dispatch(self, request: Request, call_next):\n        if request.url.path in SKIP_PATHS:\n            return await call_next(request)\n        tenant_id = request.headers.get("X-Tenant-Id", "").strip()\n        if not tenant_id:\n            return JSONResponse(\n                status_code=400,\n                content={"detail": "X-Tenant-Id header is required"},\n            )\n        request.state.tenant_id = tenant_id\n        return await call_next(request)\n'

FILES['middleware.py'] = LIC + 'import uuid\nfrom fastapi import Request\nfrom starlette.middleware.base import BaseHTTPMiddleware\n\n\nclass RequestIDMiddleware(BaseHTTPMiddleware):\n    """Attach a unique X-Request-ID to every request and response."""\n\n    async def dispatch(self, request: Request, call_next):\n        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())\n        request.state.request_id = request_id\n        response = await call_next(request)\n        response.headers["X-Request-ID"] = request_id\n        return response\n'

FILES['ratelimit.py'] = LIC + 'from datetime import datetime, timezone\nfrom fastapi import Request\nfrom fastapi.responses import JSONResponse\nfrom starlette.middleware.base import BaseHTTPMiddleware\n\n# Limits per UTC day per tenant\n# /mcare/auto 100   /clinical-cases 200   default 1000\nLIMITS: dict[str, int] = {\n    "/mcare/auto": 100,\n    "/clinical-cases": 200,\n}\nDEFAULT_LIMIT = 1_000\n_counters: dict[str, int] = {}  # TODO Phase15-prod: move to PostgreSQL\n\n\ndef _today_utc() -> str:\n    return datetime.now(timezone.utc).strftime("%Y-%m-%d")\n\n\nclass RateLimitMiddleware(BaseHTTPMiddleware):\n    """Tenant-scoped UTC-day rate limiter. Returns 429 when limit exceeded."""\n\n    async def dispatch(self, request: Request, call_next):\n        tenant_id = (\n            getattr(request.state, "tenant_id", None)\n            or request.headers.get("X-Tenant-Id", "anonymous").strip()\n        )\n        path = request.url.path\n        limit = LIMITS.get(path, DEFAULT_LIMIT)\n        key = f"{tenant_id}:{path}:{_today_utc()}"\n        _counters[key] = _counters.get(key, 0) + 1\n        if _counters[key] > limit:\n            return JSONResponse(\n                status_code=429,\n                content={"detail": "rate limit exceeded"},\n            )\n        return await call_next(request)\n'

FILES['errorhandlers.py'] = LIC + 'from fastapi import FastAPI, HTTPException, Request\nfrom fastapi.responses import JSONResponse\n\n\ndef register_error_handlers(app: FastAPI) -> None:\n    """Register global HTTP exception handlers."""\n\n    @app.exception_handler(HTTPException)\n    async def http_exc_handler(request: Request, exc: HTTPException) -> JSONResponse:\n        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})\n\n    @app.exception_handler(404)\n    async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:\n        return JSONResponse(status_code=404, content={"detail": "Not found"})\n\n    @app.exception_handler(500)\n    async def server_error_handler(request: Request, exc: Exception) -> JSONResponse:\n        return JSONResponse(status_code=500, content={"detail": "Internal server error"})\n'

def safe_write(name: str, body: str) -> None:
    if name in PROTECTED:
        print(f"  SKIP (PROTECTED): {name}")
        return
    target = CORE_DIR / name
    if not target.parent.exists():
        print(f"  ERROR: {target.parent} not found. Run from clincore-platform root.")
        sys.exit(1)
    target.write_text(body, encoding="utf-8")
    print(f"  OK  {target.relative_to(HERE)}  ({target.stat().st_size} bytes)")


print(f"Core dir : {CORE_DIR}")
print(f"Exists   : {CORE_DIR.exists()}")
print()

for fname, content in FILES.items():
    safe_write(fname, content)

print()
ok = all((CORE_DIR / f).exists() for f in ["rls.py", "middleware.py", "ratelimit.py", "errorhandlers.py"])
for f in ["rls.py", "middleware.py", "ratelimit.py", "errorhandlers.py"]:
    p = CORE_DIR / f
    print(f"  {'OK' if p.exists() else 'MISSING'}  {f}")

print()
if ok:
    print("Next:")
    print("  1. python -c \"import sys;sys.path.insert(0,'src');" +
          "from clincore.core.middleware import RequestIDMiddleware;" +
          "from clincore.core.ratelimit import RateLimitMiddleware;" +
          "from clincore.core.errorhandlers import register_error_handlers;" +
          "print('CORE IMPORT OK')\"")
    print("  2. pytest tests/ -v --asyncio-mode=auto")
    print("  3. git add src/clincore/core/")
    print("     git commit -m \"fix(core): rebuild rls middleware ratelimit errorhandlers\"")
else:
    sys.exit(1)
