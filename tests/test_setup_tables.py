"""Setup required tables for tests"""
import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_create_rate_limit_table(admin_engine):
    """Create rate_limit_counters table if not exists"""
    async with admin_engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS rate_limit_counters (
                id          BIGSERIAL PRIMARY KEY,
                tenant_id   UUID NOT NULL,
                endpoint    VARCHAR(120) NOT NULL,
                window_day  DATE NOT NULL,
                count       INTEGER NOT NULL DEFAULT 0,
                CONSTRAINT uq_rl_tenant_endpoint_day UNIQUE (tenant_id, endpoint, window_day)
            )
        """))
        
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_rl_tenant_day
                ON rate_limit_counters (tenant_id, window_day)
        """))
        
        await conn.execute(text("ALTER TABLE rate_limit_counters DISABLE ROW LEVEL SECURITY"))
    
    print("✅ rate_limit_counters table created")
