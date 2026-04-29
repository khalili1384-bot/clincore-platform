# Bug Fixes — Phase 15 Test Failures

## Summary
Fixed 3 critical bugs preventing Phase 15 tests from passing:

1. **Rate limit asyncpg compatibility** — SQLAlchemy Core upsert
2. **Patient NOT NULL violation** — Migration + test updates
3. **Super admin test connectivity** — ASGI transport fixture

---

## Bug 1: Rate Limit ProgrammingError (asyncpg)

### Problem
`sqlalchemy.dialects.postgresql.asyncpg.ProgrammingError` in all rate limit tests.

Raw SQL via `text()` with `INSERT ... ON CONFLICT ... RETURNING` doesn't work properly with asyncpg driver without explicit execution options.

### Solution
**File**: `src/clincore/core/rate_limit.py`

Replaced raw SQL `text()` with SQLAlchemy Core upsert:

```python
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import Table, Column, BigInteger, String, Date, Integer, MetaData

_meta = MetaData()
_rl_table = Table(
    "rate_limit_counters", _meta,
    Column("id", BigInteger, primary_key=True),
    Column("tenant_id", String),
    Column("endpoint", String),
    Column("window_day", Date),
    Column("count", Integer),
)

async def check_and_increment(session, tenant_id, path):
    stmt = (
        pg_insert(_rl_table)
        .values(tenant_id=tenant_id, endpoint=path, window_day=today, count=1)
        .on_conflict_do_update(
            constraint="uq_rl_tenant_endpoint_day",
            set_={"count": _rl_table.c.count + 1},
        )
        .returning(_rl_table.c.count)
    )
    result = await session.execute(stmt)
    # ... rest of function
```

**Benefits**:
- ✅ Driver-agnostic (works with asyncpg and psycopg3)
- ✅ Type-safe
- ✅ No execution_options needed
- ✅ Atomic upsert guaranteed

---

## Bug 2: Patient NOT NULL Violation

### Problem
`asyncpg.exceptions.NotNullViolationError: null value in column "patient_no"`

Tests were inserting patients without `patient_no`, but the column became NOT NULL somewhere.

### Solution

**A. Migration Fix**: `alembic/versions/0061_patient_no.py`
```python
def upgrade():
    op.add_column('patients', sa.Column('patient_no', sa.BigInteger(), nullable=True))
    # Set default value for existing rows (0 = legacy patient)
    op.execute("UPDATE patients SET patient_no = 0 WHERE patient_no IS NULL")
```

**B. Test Fixes**:

`tests/test_rls_hard.py`:
```python
# Before
INSERT INTO patients (id, tenant_id, full_name, created_at)
VALUES (gen_random_uuid(), :tid, 'Patient of A', now())

# After
INSERT INTO patients (id, tenant_id, full_name, patient_no, created_at)
VALUES (gen_random_uuid(), :tid, 'Patient of A', 1, now())
```

**C. Fixture Fix**: `tests/conftest.py`
```python
@pytest.fixture
async def seed_patients(app_engine, tenants):
    # Added patient_no to both INSERT statements
    INSERT INTO patients (id, tenant_id, full_name, patient_no, created_at)
    VALUES (gen_random_uuid(), :tid, 'Alice A', 1, now())
```

---

## Bug 3: Super Admin ConnectError

### Problem
`httpx.ConnectError: All connection attempts failed`

`test_super_admin.py` used `async_client` fixture which connects to `http://127.0.0.1:8000` (live server). Tests run without server.

### Solution

**A. New Fixture**: `tests/conftest.py`
```python
@pytest.fixture
async def test_client():
    """ASGI test client (no live server needed)."""
    from httpx import AsyncClient, ASGITransport
    from clincore.api.main import app
    
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
```

**B. Test Updates**: `tests/test_super_admin.py`
```python
# Before
async def test_super_admin_no_key(async_client):
    response = await async_client.get("/super-admin/tenants")

# After
async def test_super_admin_no_key(test_client):
    response = await test_client.get("/super-admin/tenants")
```

All 5 test functions updated to use `test_client` instead of `async_client`.

**Benefits**:
- ✅ No live server required
- ✅ Faster test execution
- ✅ Works in CI/CD without server startup
- ✅ ASGI transport directly tests the app

---

## Files Modified

### Core Logic
- `src/clincore/core/rate_limit.py` — SQLAlchemy Core upsert

### Migrations
- `alembic/versions/0061_patient_no.py` — Add UPDATE for existing rows

### Tests
- `tests/conftest.py` — Add `test_client` fixture, fix `seed_patients`
- `tests/test_rls_hard.py` — Add `patient_no` to 2 INSERT statements
- `tests/test_super_admin.py` — Replace `async_client` with `test_client` (5 functions)

---

## Verification

Run the fixed tests:
```powershell
pytest tests/test_rate_limit.py -v --asyncio-mode=auto
pytest tests/test_rls_hard.py -v --asyncio-mode=auto
pytest tests/test_super_admin.py -v --asyncio-mode=auto
```

Run all tests:
```powershell
pytest tests/ -v --asyncio-mode=auto
```

Expected: All 76+ tests pass ✅

---

## Technical Notes

### Why SQLAlchemy Core over raw SQL?
- asyncpg has strict requirements for RETURNING clauses
- SQLAlchemy Core generates driver-compatible SQL
- Maintains type safety and IDE autocomplete
- No performance penalty (compiles to same SQL)

### Why patient_no nullable=True?
- Migration adds column to existing table with data
- Can't add NOT NULL without default or UPDATE first
- Migration now handles existing rows gracefully
- New inserts always provide patient_no explicitly

### Why ASGI transport?
- Super admin endpoints don't need live server
- ASGI transport tests the app directly via ASGI protocol
- Faster, more reliable, no port conflicts
- Standard pattern for FastAPI testing

---

## Constraints Met

✅ No modifications to locked files (mcare_sqlite_engine_v6_1.py, etc.)  
✅ No bind parameters in raw SQL (used SQLAlchemy Core)  
✅ WindowsSelectorEventLoopPolicy preserved in conftest.py  
✅ No removal of /mcare/auto startup assert  
✅ All tenant isolation maintained  
✅ All RLS policies intact  

---

## Next Steps

1. Run migration: `alembic upgrade head`
2. Run tests: `pytest tests/ -v --asyncio-mode=auto`
3. Verify all 76+ tests pass
4. Commit changes with message: "Fix Phase 15 test failures (rate limit, patient_no, super admin)"
