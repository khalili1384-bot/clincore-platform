# Rate Limiting Implementation — ClinCore Platform

## Overview
PostgreSQL-based rate limiting with per-tenant, per-day counters. No Redis required.

## Rate Limits

| Endpoint | Limit (per UTC day) |
|----------|---------------------|
| `/mcare/auto` | 100 requests |
| `/clinical-cases*` | 200 requests |
| All other endpoints | 1000 requests |

## Architecture

### Database Schema

**Table: `rate_limit_counters`**
```sql
CREATE TABLE rate_limit_counters (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   UUID NOT NULL,
    endpoint    VARCHAR(120) NOT NULL,
    window_day  DATE NOT NULL,
    count       INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT uq_rl_tenant_endpoint_day UNIQUE (tenant_id, endpoint, window_day)
);

CREATE INDEX idx_rl_tenant_day ON rate_limit_counters (tenant_id, window_day);
```

**Table: `usage_events`** (for analytics)
```sql
CREATE TABLE usage_events (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     TEXT NOT NULL,
    endpoint_path TEXT NOT NULL,
    status_code   INTEGER NOT NULL,
    created_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

CREATE INDEX idx_usage_events_tenant_date ON usage_events (tenant_id, created_at);
```

Both tables have RLS **disabled** (infrastructure tables, not user data).

### Implementation Files

1. **Migration**: `alembic/versions/0058_rate_limit_indexes.py`
   - Creates `rate_limit_counters` and `usage_events` tables
   - Creates indexes for efficient lookups
   - Disables RLS on both tables

2. **Core Logic**: `src/clincore/core/rate_limit.py`
   - `get_limit(path)`: Returns limit for endpoint
   - `check_and_increment(session, tenant_id, path)`: Atomic upsert counter
   - Uses `INSERT ... ON CONFLICT DO UPDATE` for race-free increments

3. **Middleware**: `src/clincore/api/main.py`
   - `RateLimitMiddleware`: Checks limits before processing requests
   - Returns HTTP 429 when limit exceeded
   - Logs all requests to `usage_events` table
   - Skips: `/static`, `/panel`, `/docs`, `/super-admin`, `/auth`, `/shop`, `/store`

4. **Tests**: `tests/test_rate_limit.py`
   - Unit tests for limit constants and logic
   - Integration tests with real database
   - Tests for different tenants, endpoints, and day boundaries

## How It Works

1. **Request arrives** → Middleware extracts `X-Tenant-Id` header
2. **Check limit** → Call `check_and_increment(session, tenant_id, path)`
3. **Atomic upsert**:
   ```sql
   INSERT INTO rate_limit_counters (tenant_id, endpoint, window_day, count)
   VALUES ('tenant-123', '/mcare/auto', '2026-04-29', 1)
   ON CONFLICT (tenant_id, endpoint, window_day)
   DO UPDATE SET count = rate_limit_counters.count + 1
   RETURNING count
   ```
4. **Compare**: If `count > limit` → return HTTP 429
5. **Process request** → Continue to route handler
6. **Log usage**: Insert into `usage_events` for analytics

## Key Features

✅ **Atomic counters** — No race conditions with concurrent requests  
✅ **Per-tenant isolation** — Each tenant has separate limits  
✅ **UTC day windows** — Counters reset at midnight UTC  
✅ **Fail-open design** — If rate limit check fails, allow request  
✅ **No Redis** — Pure PostgreSQL solution  
✅ **Efficient indexes** — Fast lookups on `(tenant_id, window_day)`  

## Testing

Run all tests:
```powershell
pytest tests/test_rate_limit.py -v --asyncio-mode=auto
```

Run specific test:
```powershell
pytest tests/test_rate_limit.py::test_rate_limit_mcare_blocked -v
```

## Migration

Apply migration:
```powershell
alembic upgrade head
```

Rollback:
```powershell
alembic downgrade -1
```

## Monitoring

Query current usage:
```sql
SELECT tenant_id, endpoint, window_day, count
FROM rate_limit_counters
WHERE window_day = CURRENT_DATE
ORDER BY count DESC
LIMIT 20;
```

Query usage events:
```sql
SELECT tenant_id, endpoint_path, COUNT(*) as total_requests
FROM usage_events
WHERE created_at >= CURRENT_DATE
GROUP BY tenant_id, endpoint_path
ORDER BY total_requests DESC;
```

## Response Format

**Success (under limit)**:
- HTTP 200/201/etc. (normal response)

**Rate limit exceeded**:
```json
HTTP 429 Too Many Requests
{
  "detail": "rate limit exceeded"
}
```

## Configuration

Limits are defined in `src/clincore/core/rate_limit.py`:

```python
LIMITS = {
    "/mcare/auto": 100,
    "/clinical-cases": 200,
}
DEFAULT_LIMIT = 1000
```

To change limits, edit this file and restart the server.

## Production Considerations

1. **Database cleanup**: Old counters can be deleted after 30 days:
   ```sql
   DELETE FROM rate_limit_counters WHERE window_day < CURRENT_DATE - INTERVAL '30 days';
   ```

2. **Index maintenance**: PostgreSQL auto-vacuums, but monitor table size

3. **Connection pooling**: Uses existing SQLAlchemy async pool

4. **Error handling**: Middleware fails open if database is unavailable

## Compliance

- **Tenant isolation**: Each tenant's limits are independent
- **No PII**: Tables store only tenant IDs and endpoint paths
- **Audit trail**: `usage_events` provides complete request history
- **RLS disabled**: These are infrastructure tables, not user data
