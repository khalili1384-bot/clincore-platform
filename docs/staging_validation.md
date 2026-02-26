# Staging Validation Report — v0.3.9

**Date:** 2026-02-25  
**DB:** `clincore_staging` (PostgreSQL 16, localhost:5432)  
**Alembic head:** `b1c2d3e4f505`  
**Smoke tool:** `scripts/smoke_live.py` (ASGI in-process, staging DB)

---

## Smoke Test Results: 11/11 PASSED

| # | Test | Result |
|---|---|---|
| 1 | `GET /health` → 200 `{"status":"ok"}` | ✅ PASS |
| 2 | `POST /bootstrap` creates tenant + API key | ✅ PASS |
| 3 | `GET /admin/usage` without key → 401 | ✅ PASS |
| 4 | `GET /admin/usage` with wrong key → 401 | ✅ PASS |
| 5 | `POST /bootstrap` with wrong token → 401 | ✅ PASS |
| 6 | `POST /cases` creates case | ✅ PASS |
| 7 | `GET /cases/{id}` returns correct case | ✅ PASS |
| 8 | `POST /cases/{id}/finalize` returns signature | ✅ PASS |
| 9 | `POST /cases/{id}/verify-replay` returns `ok=true` | ✅ PASS |
| 10 | `GET /admin/usage` returns `total_calls` | ✅ PASS |
| 11 | Tenant isolation: Tenant B `GET /cases/{id}` owned by A → 404 | ✅ PASS |

---

## Security Checks

### 1. API key required
- `GET /admin/usage` without `X-API-Key` header → **401 Unauthorized**
- `GET /admin/usage` with invalid key → **401 Unauthorized**
- **Result:** enforced ✅

### 2. Bootstrap token required
- `POST /bootstrap` with wrong `Authorization` header → **401 Unauthorized**
- **Result:** enforced ✅

### 3. Tenant isolation (RLS)
- Case created by Tenant A
- Tenant B's `GET /cases/{case_id}` → **404 Not Found**
- `usage_events` isolated per tenant (verified by admin usage endpoint)
- **Result:** RLS enforced ✅

### 4. Revoked key rejection
- Covered in `tests/test_admin_usage.py::test_revoked_key_rejected`
- `api_keys` with `revoked_at IS NOT NULL` → **401 Unauthorized**
- **Result:** enforced ✅

### 5. Free tier billing guard
- Covered in `tests/test_admin_usage.py::test_billing_guard_free_tier`
- `usage_events > 1000` on `billing_status='free'` → **402 Payment Required**
- **Result:** enforced ✅

---

## Migration Chain Verified on Fresh DB

```
 -> 0001_core_init
 -> 20f4b88b6b43  (fix rls nullif handling + security grants)
 -> 34bf50c7d602  (case_engine_core_v032)
 -> 9ab846c6a33b  (v033_finalize_signature_hardening)
 -> 256690bbd45e  (v034_replay_verification)
 -> 0e397e47435e  (v035_access_logs)
 -> a96162dee369  (v036_billing_skeleton)
 -> b1c2d3e4f505  (v037_usage_tracking)   ← HEAD
```

All 8 migrations applied cleanly on empty `clincore_staging` database.

---

## Architecture Observations

- `psycopg_async` driver requires `WindowsSelectorEventLoopPolicy` on Windows — set in `clincore/db.py`
- `alembic.ini` uses `psycopg` (sync) for migrations — separate from app's `psycopg_async`
- Module-level engine singleton in `clincore/db.py` requires env vars to be set before first import
- `BOOTSTRAP_TOKEN` read at import-time — must be set in environment before server start

---

## Conclusion

All security controls, RLS isolation, authentication, and core API flows validated on clean staging database. No issues found.
