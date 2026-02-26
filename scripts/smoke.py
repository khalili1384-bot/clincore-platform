"""
scripts/smoke.py — HTTP-level smoke test for ClinCore API.

Uses ASGITransport + httpx (no network required).
Simulates: bootstrap, create case, GET case, GET /admin/usage.
Exit code: 0 = all green, 1 = any failure.
"""
from __future__ import annotations

import asyncio
import os
import secrets
import sys
import uuid

# Ensure repo src is on path
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, os.path.join(_REPO_ROOT, "src"))

import httpx
from fastapi import FastAPI

from clincore.api.bootstrap import router as bootstrap_router
from clincore.api.auth_api_keys import _hash_key, router as auth_router
from clincore.api.admin import router as admin_router
from clincore.api.case_engine import router as case_router
from clincore.db import engine
from sqlalchemy import text


RESULTS: list[dict] = []


def _pass(name: str, detail: str = "") -> None:
    RESULTS.append({"name": name, "status": "PASS", "detail": detail})
    print(f"  PASS  {name}" + (f": {detail}" if detail else ""))


def _fail(name: str, detail: str = "") -> None:
    RESULTS.append({"name": name, "status": "FAIL", "detail": detail})
    print(f"  FAIL  {name}" + (f": {detail}" if detail else ""))


def _make_full_app(bootstrap_token: str) -> FastAPI:
    import clincore.api.bootstrap as _bs
    _bs._BOOTSTRAP_TOKEN = bootstrap_token
    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    app.include_router(bootstrap_router)
    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(case_router)
    return app


async def _setup_admin_key(tenant_id: str, raw_key: str) -> str:
    """Insert an admin api_key directly for smoke test use."""
    key_id = str(uuid.uuid4())
    key_hash = _hash_key(raw_key)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO api_keys (id, tenant_id, key_hash, label, is_active, role, created_at)
                VALUES (:id, :tid, :kh, 'smoke-admin', true, 'admin', now())
                """
            ),
            {"id": key_id, "tid": tenant_id, "kh": key_hash},
        )
    return key_id


async def run_smoke() -> bool:
    print("\n=== ClinCore Smoke Tests ===\n")

    bootstrap_token = os.environ.get("BOOTSTRAP_TOKEN", "smoke-test-token-" + secrets.token_hex(8))

    import clincore.api.bootstrap as _bs
    _bs._BOOTSTRAP_TOKEN = bootstrap_token

    tenant_name = f"smoke_{uuid.uuid4().hex[:8]}"
    app = _make_full_app(bootstrap_token)
    transport = httpx.ASGITransport(app=app)

    # ── 1. Health check ────────────────────────────────────────────────────
    print("1. Health check")
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get("/health")
        if resp.status_code == 200 and resp.json().get("status") == "ok":
            _pass("GET /health")
        else:
            _fail("GET /health", f"status={resp.status_code} body={resp.text[:200]}")
    except Exception as exc:
        _fail("GET /health", str(exc))

    # ── 2. Bootstrap ───────────────────────────────────────────────────────
    print("2. Bootstrap tenant")
    raw_key = None
    tenant_id = None
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post(
                "/bootstrap",
                json={"tenant_name": tenant_name},
                headers={"Authorization": f"Bearer {bootstrap_token}"},
            )
        if resp.status_code == 201:
            data = resp.json()
            tenant_id = data["tenant_id"]
            raw_key = data["api_key"]
            _pass("POST /bootstrap", f"tenant_id={tenant_id[:8]}...")
        else:
            _fail("POST /bootstrap", f"status={resp.status_code} body={resp.text[:200]}")
    except Exception as exc:
        _fail("POST /bootstrap", str(exc))

    if not tenant_id or not raw_key:
        print("\nSkipping remaining tests — bootstrap failed.\n")
        return False

    # Promote bootstrap key to admin role for /admin/* endpoints
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("UPDATE api_keys SET role='admin' WHERE tenant_id=:tid"),
                {"tid": tenant_id},
            )
    except Exception as exc:
        _fail("Promote key to admin role", str(exc))

    # Insert a patient for case creation
    patient_id = str(uuid.uuid4())
    try:
        from clincore.db import tenant_session
        async with tenant_session(tenant_id) as session:
            await session.execute(
                text(
                    "INSERT INTO patients (id, tenant_id, full_name, created_at) "
                    "VALUES (:id, :tid, 'Smoke Patient', now())"
                ),
                {"id": patient_id, "tid": tenant_id},
            )
    except Exception as exc:
        _fail("Insert smoke patient", str(exc))

    # ── 3. Create case ─────────────────────────────────────────────────────
    print("3. Create case")
    case_id = None
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post(
                "/cases",
                headers={"X-Tenant-ID": tenant_id},
                json={"patient_id": patient_id, "input_payload": {"symptom_ids": [1, 2]}},
            )
        if resp.status_code == 200:
            case_id = resp.json()["case_id"]
            _pass("POST /cases", f"case_id={str(case_id)[:8]}...")
        else:
            _fail("POST /cases", f"status={resp.status_code} body={resp.text[:200]}")
    except Exception as exc:
        _fail("POST /cases", str(exc))

    # ── 4. GET case ────────────────────────────────────────────────────────
    if case_id:
        print("4. GET case")
        try:
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.get(
                    f"/cases/{case_id}",
                    headers={"X-Tenant-ID": tenant_id},
                )
            if resp.status_code == 200 and str(resp.json()["id"]) == str(case_id):
                _pass("GET /cases/{id}")
            else:
                _fail("GET /cases/{id}", f"status={resp.status_code} body={resp.text[:200]}")
        except Exception as exc:
            _fail("GET /cases/{id}", str(exc))

    # ── 5. GET /admin/usage ────────────────────────────────────────────────
    print("5. GET /admin/usage")
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get(
                "/admin/usage",
                headers={"X-API-Key": raw_key},
            )
        if resp.status_code == 200 and "total_calls" in resp.json():
            _pass("GET /admin/usage", f"total_calls={resp.json()['total_calls']}")
        else:
            _fail("GET /admin/usage", f"status={resp.status_code} body={resp.text[:200]}")
    except Exception as exc:
        _fail("GET /admin/usage", str(exc))

    # ── Summary ────────────────────────────────────────────────────────────
    total = len(RESULTS)
    passed = sum(1 for r in RESULTS if r["status"] == "PASS")
    failed = total - passed

    print(f"\n=== Smoke Summary: {passed}/{total} passed ===")
    if failed:
        print(f"FAILED checks ({failed}):")
        for r in RESULTS:
            if r["status"] == "FAIL":
                print(f"  - {r['name']}: {r['detail']}")
        return False

    return True


def main() -> None:
    ok = asyncio.run(run_smoke())
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
