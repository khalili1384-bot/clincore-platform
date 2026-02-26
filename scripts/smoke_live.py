"""
scripts/smoke_live.py — Staging smoke test using ASGI transport against staging DB.

Runs entirely in-process against clincore_staging database.
No live uvicorn required — avoids module-level engine singleton issue.

Usage:
    python scripts/smoke_live.py [--bootstrap-token TOKEN] [--db-url URL]

Exit code: 0 = all green, 1 = any failure.
"""
from __future__ import annotations

# Step 1: event loop policy FIRST on Windows
import asyncio
import sys
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import argparse
import os
import uuid

RESULTS: list[dict] = []


def _pass(name: str, detail: str = "") -> None:
    RESULTS.append({"name": name, "status": "PASS", "detail": detail})
    print(f"  PASS  {name}" + (f": {detail}" if detail else ""))


def _fail(name: str, detail: str = "") -> None:
    RESULTS.append({"name": name, "status": "FAIL", "detail": detail})
    print(f"  FAIL  {name}" + (f": {detail}" if detail else ""))


async def run_smoke(bootstrap_token: str, db_url: str) -> bool:
    print(f"\n=== ClinCore Staging Smoke Tests ===")
    print(f"DB: {db_url.split('@')[-1]}\n")

    # Step 2: patch env and engine BEFORE importing app modules
    os.environ["DATABASE_URL"] = db_url
    os.environ["BOOTSTRAP_TOKEN"] = bootstrap_token
    os.environ.setdefault("REPERTORY_DB_PATH", "data/clinical.db")

    # Clear settings cache so new DATABASE_URL is picked up
    import clincore.config as _cfg
    _cfg.get_settings.cache_clear()

    # Rebuild engine with staging URL using db.py helpers (avoids raw create_async_engine)
    import clincore.db as _db
    staging_engine = _db.make_engine(db_url)
    staging_session = _db.make_session_factory(staging_engine)
    _db.engine = staging_engine
    _db.SessionLocal = staging_session

    # Patch all api module _engine references (they bind at import-time)
    import clincore.api.bootstrap as _bs
    import clincore.api.auth_api_keys as _auth
    import clincore.api.admin as _adm
    import clincore.api.case_engine  # ensure imported

    _bs._engine = staging_engine
    _auth._engine = staging_engine
    _adm._engine = staging_engine

    # Patch tenant_session to use staging SessionLocal
    import contextlib
    from typing import AsyncIterator
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy import text as _text

    @contextlib.asynccontextmanager
    async def _staging_tenant_session(tenant_id: str):
        if not tenant_id:
            raise ValueError("tenant_id required")
        async with staging_session() as session:
            async with session.begin():
                await session.execute(_text(f"SET LOCAL app.tenant_id = '{tenant_id}'"))
                yield session

    _db.tenant_session = _staging_tenant_session
    _bs.tenant_session = _staging_tenant_session if hasattr(_bs, 'tenant_session') else None
    _auth.tenant_session = _staging_tenant_session
    _adm.tenant_session = _staging_tenant_session

    # Patch bootstrap token
    _bs._BOOTSTRAP_TOKEN = bootstrap_token

    # Build test app
    from fastapi import FastAPI
    import httpx
    from clincore.api.bootstrap import router as bootstrap_router
    from clincore.api.auth_api_keys import router as auth_router
    from clincore.api.admin import router as admin_router
    from clincore.api.case_engine import router as case_router

    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    app.include_router(bootstrap_router)
    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(case_router)

    transport = httpx.ASGITransport(app=app)

    tenant_id = None
    raw_key = None
    case_id = None

    async with httpx.AsyncClient(transport=transport, base_url="http://staging") as client:

        # ── 1. Health check ───────────────────────────────────────────────
        print("1. Health check")
        try:
            r = await client.get("/health")
            if r.status_code == 200 and r.json().get("status") == "ok":
                _pass("GET /health")
            else:
                _fail("GET /health", f"status={r.status_code}")
                return False
        except Exception as exc:
            _fail("GET /health", str(exc))
            return False

        # ── 2. Bootstrap ──────────────────────────────────────────────────
        print("2. Bootstrap tenant")
        tenant_name = f"staging_smoke_{uuid.uuid4().hex[:8]}"
        try:
            r = await client.post(
                "/bootstrap",
                json={"tenant_name": tenant_name},
                headers={"Authorization": f"Bearer {bootstrap_token}"},
            )
            if r.status_code == 201:
                data = r.json()
                tenant_id = data["tenant_id"]
                raw_key = data["api_key"]
                _pass("POST /bootstrap", f"tenant_id={tenant_id[:8]}...")
            else:
                _fail("POST /bootstrap", f"status={r.status_code} body={r.text[:300]}")
                return False
        except Exception as exc:
            _fail("POST /bootstrap", str(exc))
            return False

        # ── 3. Security: missing API key → 401 ───────────────────────────
        print("3. Security: no API key → 401")
        try:
            r = await client.get("/admin/usage")
            if r.status_code == 401:
                _pass("GET /admin/usage without key → 401")
            else:
                _fail("GET /admin/usage no-key should be 401", f"got {r.status_code}")
        except Exception as exc:
            _fail("no-key security check", str(exc))

        # ── 4. Security: wrong API key → 401 ─────────────────────────────
        print("4. Security: wrong API key → 401")
        try:
            r = await client.get("/admin/usage", headers={"X-API-Key": "wrong-key-xyz"})
            if r.status_code == 401:
                _pass("Wrong API key → 401")
            else:
                _fail("Wrong API key should be 401", f"got {r.status_code}")
        except Exception as exc:
            _fail("wrong-key security check", str(exc))

        # ── 5. Security: wrong bootstrap token → 401 ─────────────────────
        print("5. Security: wrong bootstrap token → 401")
        try:
            r = await client.post(
                "/bootstrap",
                json={"tenant_name": "should_fail"},
                headers={"Authorization": "Bearer wrong-bootstrap-token"},
            )
            if r.status_code == 401:
                _pass("Wrong bootstrap token → 401")
            else:
                _fail("Wrong bootstrap token should be 401", f"got {r.status_code}")
        except Exception as exc:
            _fail("bootstrap token security check", str(exc))

        # Promote bootstrap key to admin for /admin/* endpoints
        try:
            async with _db.engine.begin() as conn:
                from sqlalchemy import text
                await conn.execute(
                    text("UPDATE api_keys SET role='admin' WHERE tenant_id=:tid"),
                    {"tid": tenant_id},
                )
        except Exception as exc:
            _fail("Promote key to admin", str(exc))

        # Insert test patient
        patient_id = str(uuid.uuid4())
        try:
            from clincore.db import tenant_session
            async with tenant_session(tenant_id) as session:
                from sqlalchemy import text
                await session.execute(
                    text(
                        "INSERT INTO patients (id, tenant_id, full_name, created_at) "
                        "VALUES (:id, :tid, 'Smoke Patient', now())"
                    ),
                    {"id": patient_id, "tid": tenant_id},
                )
        except Exception as exc:
            _fail("Insert test patient", str(exc))

        # ── 6. Create case ────────────────────────────────────────────────
        print("6. Create case")
        try:
            r = await client.post(
                "/cases",
                headers={"X-Tenant-ID": tenant_id},
                json={"patient_id": patient_id, "input_payload": {"symptom_ids": [1, 2]}},
            )
            if r.status_code == 200:
                case_id = r.json()["case_id"]
                _pass("POST /cases", f"case_id={str(case_id)[:8]}...")
            else:
                _fail("POST /cases", f"status={r.status_code} body={r.text[:300]}")
        except Exception as exc:
            _fail("POST /cases", str(exc))

        # ── 7. GET case ───────────────────────────────────────────────────
        if case_id:
            print("7. GET case")
            try:
                r = await client.get(f"/cases/{case_id}", headers={"X-Tenant-ID": tenant_id})
                if r.status_code == 200 and str(r.json()["id"]) == str(case_id):
                    _pass("GET /cases/{id}")
                else:
                    _fail("GET /cases/{id}", f"status={r.status_code}")
            except Exception as exc:
                _fail("GET /cases/{id}", str(exc))

            # ── 8. Finalize case ──────────────────────────────────────────
            print("8. Finalize case")
            try:
                r = await client.post(f"/cases/{case_id}/finalize", headers={"X-Tenant-ID": tenant_id})
                if r.status_code == 200 and r.json().get("status") == "finalized":
                    _pass("POST /cases/{id}/finalize", f"sig={r.json()['signature'][:16]}...")
                else:
                    _fail("POST /cases/{id}/finalize", f"status={r.status_code} body={r.text[:200]}")
            except Exception as exc:
                _fail("POST /cases/{id}/finalize", str(exc))

            # ── 9. Verify replay ──────────────────────────────────────────
            print("9. Verify replay")
            try:
                r = await client.post(f"/cases/{case_id}/verify-replay", headers={"X-Tenant-ID": tenant_id})
                if r.status_code == 200 and r.json().get("ok") is True:
                    _pass("POST /cases/{id}/verify-replay")
                else:
                    _fail("POST /cases/{id}/verify-replay", f"status={r.status_code} body={r.text[:200]}")
            except Exception as exc:
                _fail("POST /cases/{id}/verify-replay", str(exc))

        # ── 10. GET /admin/usage ──────────────────────────────────────────
        print("10. GET /admin/usage")
        try:
            r = await client.get("/admin/usage", headers={"X-API-Key": raw_key})
            if r.status_code == 200 and "total_calls" in r.json():
                _pass("GET /admin/usage", f"total_calls={r.json()['total_calls']}")
            else:
                _fail("GET /admin/usage", f"status={r.status_code} body={r.text[:200]}")
        except Exception as exc:
            _fail("GET /admin/usage", str(exc))

        # ── 11. Tenant isolation ──────────────────────────────────────────
        if case_id:
            print("11. Tenant isolation: tenant B cannot see tenant A's case")
            tenant_b_id = str(uuid.uuid4())
            try:
                async with _db.engine.begin() as conn:
                    from sqlalchemy import text
                    await conn.execute(
                        text("INSERT INTO tenants (id, name, created_at) VALUES (:id, :name, now())"),
                        {"id": tenant_b_id, "name": f"isolation_b_{uuid.uuid4().hex[:6]}"},
                    )
                r = await client.get(f"/cases/{case_id}", headers={"X-Tenant-ID": tenant_b_id})
                if r.status_code == 404:
                    _pass("Tenant isolation: B cannot see A's case → 404")
                else:
                    _fail("Tenant isolation BROKEN", f"Tenant B got status={r.status_code}")
            except Exception as exc:
                _fail("Tenant isolation check", str(exc))

    # ── Summary ───────────────────────────────────────────────────────────
    total = len(RESULTS)
    passed = sum(1 for r in RESULTS if r["status"] == "PASS")
    failed = total - passed

    print(f"\n=== Staging Smoke Summary: {passed}/{total} passed ===")
    if failed:
        print(f"FAILED ({failed}):")
        for r in RESULTS:
            if r["status"] == "FAIL":
                print(f"  - {r['name']}: {r['detail']}")
        return False

    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="ClinCore staging smoke test")
    parser.add_argument(
        "--bootstrap-token",
        default=os.environ.get("BOOTSTRAP_TOKEN", "staging-bootstrap-2026"),
    )
    parser.add_argument(
        "--db-url",
        default=os.environ.get(
            "STAGING_DB_URL",
            "postgresql+psycopg_async://clincore_user:805283631@127.0.0.1:5432/clincore_staging",
        ),
    )
    args = parser.parse_args()
    ok = asyncio.run(run_smoke(args.bootstrap_token, args.db_url))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
