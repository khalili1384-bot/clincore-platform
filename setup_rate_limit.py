import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        host='127.0.0.1',
        port=5432,
        user='clincore_user',
        password='805283631',
        database='clincore'
    )
    
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS rate_limit_counters (
            id          BIGSERIAL PRIMARY KEY,
            tenant_id   UUID NOT NULL,
            endpoint    VARCHAR(120) NOT NULL,
            window_day  DATE NOT NULL,
            count       INTEGER NOT NULL DEFAULT 0,
            CONSTRAINT uq_rl_tenant_endpoint_day UNIQUE (tenant_id, endpoint, window_day)
        )
    """)
    
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_rl_tenant_day
            ON rate_limit_counters (tenant_id, window_day)
    """)
    
    await conn.execute("ALTER TABLE rate_limit_counters DISABLE ROW LEVEL SECURITY")
    
    print("✅ rate_limit_counters table created")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
