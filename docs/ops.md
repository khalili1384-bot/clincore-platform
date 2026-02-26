# ClinCore Operations Runbook

## 1. Environment Requirements

### Runtime
- **Python 3.11** (exact — psycopg3 async requires 3.11 on Windows)
- **PostgreSQL** with Row Level Security (RLS) enabled per-table
- All migrations applied via Alembic before starting the server

### Required Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | **Yes** | Async PostgreSQL DSN. Format: `postgresql+psycopg://user:pass@host:5432/dbname` |
| `BOOTSTRAP_TOKEN` | **Yes (first deploy only)** | Secret token for `POST /bootstrap`. Set once, use once, then remove or rotate. |

### Optional
| Variable | Default | Description |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Logging level for `clincore.*` loggers |

---

## 2. First Deployment Procedure

Execute in exact order:

```bash
pip install -e .
alembic upgrade head
```

Verify single Alembic head:
```bash
alembic heads
# Expected output: b1c2d3e4f505 (head)
```

### Provision first tenant and API key

Set `BOOTSTRAP_TOKEN` in environment, then:

```bash
curl -X POST http://localhost:8000/bootstrap \
  -H "Authorization: Bearer $BOOTSTRAP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tenant_name": "your-org-name"}'
```

Response:
```json
{
  "tenant_id": "<uuid>",
  "api_key": "<raw-key>",
  "message": "Tenant 'your-org-name' provisioned."
}
```

**Save `api_key` securely** — it is shown only once (plaintext).

After provisioning, remove or rotate `BOOTSTRAP_TOKEN`:
```bash
unset BOOTSTRAP_TOKEN
```

---

## 3. Production Safety Notes

### API Key Security
- API keys are stored as SHA-256 hashes only. Plaintext is never stored.
- The raw key is returned **only at creation time** via `POST /bootstrap` or `POST /auth/api-keys/rotate`.
- Never log, commit, or expose the raw key.
- Revoke compromised keys via `POST /admin/api-keys/revoke/{key_id}`.

### RLS Enforcement
- Every tenant-scoped table has a PostgreSQL RLS policy: `tenant_id = current_setting('app.tenant_id')::uuid`.
- `tenant_session()` sets `SET LOCAL app.tenant_id` inside a transaction — resets automatically on transaction end.
- **Never** use `engine.begin()` directly for tenant-scoped data outside tests.
- Superuser / `bypassrls` is never used in application code.

### Free Tier Soft Billing Cap
- When `billing_status = 'free'` (default) and `COUNT(usage_events) > 1000` for a tenant:
  `POST /cases` returns `402 Payment Required`.
- To upgrade a tenant: `UPDATE cases SET billing_status = 'paid' WHERE tenant_id = '<uuid>'`.
- No payment integration is wired — this is a soft guard only.

### API Key Role
- Keys have a `role` column: `'user'` (default) or `'admin'`.
- Admin-role keys are required for all `/admin/*` endpoints.
- Bootstrap-created keys have label `bootstrap-<tenant_name>`. Update role manually if needed:
  ```sql
  UPDATE api_keys SET role = 'admin' WHERE id = '<key-uuid>';
  ```

---

## 4. Quick Health Check

### Live endpoint check
```bash
GET /health
# Expected: {"status": "ok"}
```

### Admin usage check (requires admin API key)
```bash
curl http://localhost:8000/admin/usage \
  -H "X-API-Key: <your-admin-key>"
# Returns: total_calls, calls_by_endpoint, last_24h_count
```

### Run test suite
```bash
pytest -q
# Expected: all tests passing, no failures
```

### Check Alembic migration state
```bash
alembic current
# Must match: b1c2d3e4f505
alembic heads
# Must show single head: b1c2d3e4f505 (head)
```

### Check for pending migrations
```bash
alembic check
# Expected: No new upgrade operations detected.
```
