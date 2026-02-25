import asyncio
import os
import sys

# ---- FIX WINDOWS + PSYCOPG ASYNC ----
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg_async://clincore_user:805283631@127.0.0.1:5432/clincore",
)


@pytest.fixture(scope="session")
def app_engine():
    return create_async_engine(DATABASE_URL, pool_pre_ping=True)


@pytest.fixture(scope="session")
def admin_engine():
    return create_async_engine(DATABASE_URL, pool_pre_ping=True)


@pytest.fixture
async def tenants(admin_engine):
    async with admin_engine.begin() as conn:
        await conn.execute(text("""
            INSERT INTO tenants (id, name)
            VALUES (gen_random_uuid(), 'tenant_a'),
                   (gen_random_uuid(), 'tenant_b')
            ON CONFLICT (name) DO NOTHING
        """))

        rows = (
            await conn.execute(
                text(
                    """
                    SELECT id, name
                    FROM tenants
                    WHERE name IN ('tenant_a', 'tenant_b')
                    ORDER BY name
                    """
                )
            )
        ).fetchall()

    ids_by_name = {name: tid for tid, name in rows}
    return str(ids_by_name["tenant_a"]), str(ids_by_name["tenant_b"])


@pytest.fixture
async def seed_patients(app_engine, tenants):
    tenant_a, tenant_b = tenants

    async with app_engine.begin() as conn:
        await conn.execute(text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": tenant_a})
        await conn.execute(text("DELETE FROM patients WHERE full_name = 'Alice A'"))
        await conn.execute(text("""
            INSERT INTO patients (id, tenant_id, full_name, created_at)
            VALUES (gen_random_uuid(), :tid, 'Alice A', now())
        """), {"tid": tenant_a})

    async with app_engine.begin() as conn:
        await conn.execute(text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": tenant_b})
        await conn.execute(text("DELETE FROM patients WHERE full_name = 'Bob B'"))
        await conn.execute(text("""
            INSERT INTO patients (id, tenant_id, full_name, created_at)
            VALUES (gen_random_uuid(), :tid, 'Bob B', now())
        """), {"tid": tenant_b})

    return tenant_a, tenant_b
