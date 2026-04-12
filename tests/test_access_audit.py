"""Test access audit logging and RLS"""
import pytest
from sqlalchemy import text
from uuid import uuid4


@pytest.mark.asyncio
async def test_access_audit_view_and_verify(admin_engine, tenants):
    """Test that access_logs are created and tenant-isolated"""
    t1, t2 = tenants
    
    async with admin_engine.begin() as conn:
        # Set tenant context for t1
        await conn.execute(text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": t1})
        
        # Insert access log for t1
        await conn.execute(
            text("""
                INSERT INTO access_logs (id, tenant_id, user_id, action, resource, created_at)
                VALUES (gen_random_uuid(), :tid, gen_random_uuid(), 'view', 'patient', now())
            """),
            {"tid": t1}
        )
        
        # Verify we can see it
        result = await conn.execute(text("SELECT COUNT(*) FROM access_logs"))
        count = result.scalar()
        assert count == 1, f"Expected 1 access log, got {count}"


@pytest.mark.asyncio
async def test_access_audit_tenant_isolation(admin_engine, tenants):
    """Test that access_logs respect RLS tenant isolation"""
    t1, t2 = tenants
    
    async with admin_engine.begin() as conn:
        # Insert for t1
        await conn.execute(text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": t1})
        await conn.execute(
            text("""
                INSERT INTO access_logs (id, tenant_id, user_id, action, resource, created_at)
                VALUES (gen_random_uuid(), :tid, gen_random_uuid(), 'create', 'case', now())
            """),
            {"tid": t1}
        )
        
    async with admin_engine.begin() as conn:
        # Switch to t2 context
        await conn.execute(text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": t2})
        
        # Should see 0 rows (t1's log is hidden)
        result = await conn.execute(text("SELECT COUNT(*) FROM access_logs"))
        count = result.scalar()
        assert count == 0, f"CROSS-TENANT LEAK: tenant {t2} saw {count} access_logs from tenant {t1}"
