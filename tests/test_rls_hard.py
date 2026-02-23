# tests/test_rls_hard.py
# Phase 2a — RLS Hard Test Suite
# Run: pytest -q tests/test_rls_hard.py

import pytest
import asyncio
import uuid
from sqlalchemy import text
from clincore.db import engine, tenant_session


@pytest.fixture(scope="module")
def event_loop():
    """Windows-safe event loop for pytest-asyncio."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def raw_conn():
    """Raw connection with no tenant context."""
    async with engine.connect() as conn:
        yield conn
        await conn.rollback()


@pytest.fixture
async def real_tenant(raw_conn):
    """Create a real tenant WITHOUT using tenant_session."""
    tid = uuid.uuid4()
    await raw_conn.execute(
        text("INSERT INTO tenants (id, name, created_at) VALUES (:id, :name, now())"),
        {"id": str(tid), "name": f"test_tenant_{tid.hex[:8]}"},
    )
    await raw_conn.commit()
    return tid


@pytest.mark.asyncio
async def test_cross_tenant_cannot_see_data(real_tenant):
    tenant_a = real_tenant
    tenant_b = uuid.uuid4()

    # Insert under tenant A
    async with tenant_session(str(tenant_a)) as s:
        await s.execute(
            text("""
                INSERT INTO patients (id, tenant_id, full_name, created_at)
                VALUES (gen_random_uuid(), :tid, 'Patient of A', now())
            """),
            {"tid": str(tenant_a)},
        )
        await s.flush()

    # Read under tenant B -> must be 0
    async with tenant_session(str(tenant_b)) as s:
        r = await s.execute(text("SELECT COUNT(*) FROM patients"))
        count = r.scalar()
        assert count == 0, f"CROSS-TENANT LEAK: tenant B saw {count} rows from tenant A"


@pytest.mark.asyncio
async def test_concurrent_tenants_isolated():
    tid_1 = uuid.uuid4()
    tid_2 = uuid.uuid4()

    async def get_context(tid: uuid.UUID) -> str:
        async with tenant_session(str(tid)) as s:
            await asyncio.sleep(0.05)
            r = await s.execute(text("SELECT current_setting('app.tenant_id', true)"))
            return r.scalar()

    results = await asyncio.gather(get_context(tid_1), get_context(tid_2))

    assert results[0] == str(tid_1), f"tenant_1 context polluted: {results[0]}"
    assert results[1] == str(tid_2), f"tenant_2 context polluted: {results[1]}"


@pytest.mark.asyncio
async def test_malicious_insert_blocked(real_tenant):
    my_tid = real_tenant
    fake_tid = uuid.uuid4()

    async with tenant_session(str(my_tid)) as s:
        with pytest.raises(Exception) as exc_info:
            await s.execute(
                text("""
                    INSERT INTO patients (id, tenant_id, full_name, created_at)
                    VALUES (gen_random_uuid(), :fake_tid, 'Malicious Row', now())
                """),
                {"fake_tid": str(fake_tid)},
            )
            await s.flush()

        err = str(exc_info.value).lower()
        assert any(k in err for k in ("policy", "row-level", "rls", "violat", "check")), \
            f"Unexpected error (not RLS-related): {exc_info.value}"


@pytest.mark.asyncio
async def test_clincore_user_has_no_bypassrls():
    async with engine.connect() as conn:
        r = await conn.execute(text("""
            SELECT rolbypassrls
            FROM pg_roles
            WHERE rolname = 'clincore_user'
        """))
        row = r.fetchone()
        assert row is not None, "clincore_user role not found"
        assert row[0] is False, "SECURITY: clincore_user has BYPASSRLS=true"


@pytest.mark.asyncio
async def test_tenant_context_resets_after_session():
    tid = uuid.uuid4()

    async with tenant_session(str(tid)) as s:
        r = await s.execute(text("SELECT current_setting('app.tenant_id', true)"))
        assert r.scalar() == str(tid), "tenant context was not set inside tenant_session"

    async with engine.connect() as conn:
        try:
            r = await conn.execute(text("SHOW app.tenant_id"))
            val = r.scalar()
            assert val != str(tid), f"CONTEXT LEAK: tenant_id still set after session: {val}"
        except Exception as e:
            # If the custom GUC doesn't exist at all, that's also "clean"
            if "unrecognized" in str(e).lower():
                pass
            else:
                raise


@pytest.mark.asyncio
async def test_select_without_context_returns_zero():
    async with engine.connect() as conn:
        try:
            await conn.execute(text("RESET app.tenant_id"))
        except Exception:
            pass

        r = await conn.execute(text("SELECT COUNT(*) FROM patients"))
        count = r.scalar()
        assert count == 0, f"RLS FAIL-OPEN: {count} rows visible without tenant context"