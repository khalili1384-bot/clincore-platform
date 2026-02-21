import asyncio
import os
import sys

# ---- FIX WINDOWS + PSYCOPG ASYNC ----
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


@pytest.fixture(scope="session")
def app_engine():
    return create_async_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)


@pytest.fixture(scope="session")
def admin_engine():
    return create_async_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)


@pytest.fixture
async def tenants(admin_engine):
    async with admin_engine.begin() as conn:
        await conn.execute(text("""
            INSERT INTO tenants (id, name)
            VALUES (gen_random_uuid(), 'tenant_a'),
                   (gen_random_uuid(), 'tenant_b')
        """))


@pytest.fixture
async def seed_patients(app_engine, tenants):
    async with app_engine.begin() as conn:
        # intentionally no tenant context set
        await conn.execute(text("""
            INSERT INTO patients (id, tenant_id, first_name, last_name)
            SELECT gen_random_uuid(), t.id, 'John', 'Doe'
            FROM tenants t
        """))
