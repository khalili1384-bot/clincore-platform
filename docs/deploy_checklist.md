# Deployment Checklist — ClinCore Platform

## Required Environment Variables

| Variable | Required | Notes |
|---|---|---|
| `DATABASE_URL` | **Yes** | Format: `postgresql+psycopg_async://user:pass@host:5432/dbname` — must use `127.0.0.1` not `localhost` |
| `BOOTSTRAP_TOKEN` | **Yes (first deploy only)** | Arbitrary secret string. Used once to create first tenant. Remove after use. |
| `REPERTORY_DB_PATH` | **Yes** | Path to SQLite MCARE engine database. Example: `data/clinical.db` |

---

## Migration Steps

### 1. Verify single Alembic head
```
alembic heads
# Expected: b1c2d3e4f505 (head)
```

### 2. Apply all migrations to a fresh database
```
alembic upgrade head
```

### 3. Verify migration applied
```
alembic current
# Expected: b1c2d3e4f505 (head)
```

### 4. Verify tables created (psql)
```sql
\dt
-- Expected tables: tenants, patients, cases, access_logs, api_keys, usage_events, alembic_version
```

---

## RLS Verification Query

Run as the application user (not superuser) to confirm RLS is enforced:

```sql
-- As clincore_user (no app.tenant_id set):
SELECT * FROM cases;
-- Expected: 0 rows (RLS blocks all rows without tenant context)

-- As clincore_user with tenant context:
SELECT set_config('app.tenant_id', '<uuid>', true);
SELECT COUNT(*) FROM cases;
-- Expected: only rows for that tenant
```

Verify RLS policy exists on each tenant-scoped table:
```sql
SELECT tablename, policyname, cmd
FROM pg_policies
WHERE schemaname = 'public'
ORDER BY tablename;
-- Expected: tenant_isolation policy on cases, patients, access_logs, api_keys, usage_events
```

---

## API Key Rotation Procedure

1. Generate new key via API:
   ```
   POST /auth/api-keys/rotate
   Header: X-API-Key: <current-key>
   ```
   Response includes `new_key` — save it immediately (shown once only).

2. Update all clients to use the new key.

3. Confirm old key no longer works:
   ```
   GET /health
   Header: X-API-Key: <old-key>
   # Expected: 401
   ```

4. To revoke a specific key without rotation:
   ```
   POST /admin/api-keys/revoke/{key_id}
   Header: X-API-Key: <admin-key>
   ```

---

## Backup Recommendation

### Before each migration
```bash
pg_dump -U postgres -Fc clincore > clincore_backup_$(date +%Y%m%d_%H%M%S).dump
```

### Restore from backup
```bash
pg_restore -U postgres -d clincore_new clincore_backup_YYYYMMDD_HHMMSS.dump
```

### Automated daily backup (cron example)
```
0 2 * * * pg_dump -U postgres -Fc clincore > /backups/clincore_$(date +\%Y\%m\%d).dump
```

---

## Rollback Steps

### Rollback one migration
```
alembic downgrade -1
```

### Rollback to specific revision
```
alembic downgrade <revision_id>
```

### Rollback all migrations (empty DB)
```
alembic downgrade base
```

### Revision history reference
| Revision | Description |
|---|---|
| `b1c2d3e4f505` | v037 usage_tracking + admin surface |
| `a96162dee369` | v036 billing skeleton + api_keys |
| `0e397e47435e` | v035 access_logs |
| `256690bbd45e` | v034 replay_verification |
| `9ab846c6a33b` | v033 finalize signature hardening |
| `34bf50c7d602` | v032 case engine core |
| `20f4b88b6b43` | RLS nullif fix + security grants |
| `0001_core_init` | Initial tables |

### After rollback: verify
```
alembic current
alembic heads
pytest -q
```

---

## Post-Deployment Health Check

```bash
# 1. API alive
curl http://your-host:8000/health
# Expected: {"status":"ok"}

# 2. Admin usage (requires admin API key)
curl http://your-host:8000/admin/usage \
  -H "X-API-Key: <admin-key>"
# Expected: {"total_calls": <n>, "calls_by_endpoint": {...}, "last_24h_count": <n>}

# 3. Migration state
alembic current
# Expected: b1c2d3e4f505 (head)

# 4. Test suite
pytest -q
# Expected: 40 passed
```

---

## First Deployment Sequence (Summary)

```
1. pip install -e .
2. alembic upgrade head
3. Set BOOTSTRAP_TOKEN
4. Start server: uvicorn clincore.api.main:app --port 8000
5. POST /bootstrap  → save api_key
6. Unset BOOTSTRAP_TOKEN or rotate it
7. Run: python scripts/smoke_live.py
8. Confirm: alembic current, pytest -q
```
