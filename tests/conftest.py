import asyncio
import hashlib
import os
import secrets
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import sessionmaker
import httpx

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://clincore_user:805283631@127.0.0.1:5432/clincore",
)

# Monkey patch AsyncSessionLocal with NullPool engine for tests
from clincore.core import db as db_module

_test_engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
db_module.AsyncSessionLocal = sessionmaker(_test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def app_engine():
    """Create engine with NullPool to avoid event loop conflicts in tests."""
    engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest.fixture
async def admin_engine():
    """Create engine with NullPool to avoid event loop conflicts in tests."""
    engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest.fixture
async def test_session():
    """Create a test session with NullPool engine to avoid event loop conflicts."""
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.ext.asyncio import AsyncSession
    
    engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
    TestSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with TestSessionLocal() as session:
        yield session
    
    await engine.dispose()


@pytest.fixture
async def async_client():
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=30.0) as client:
        yield client


@pytest.fixture
async def test_client():
    """ASGI test client (no live server needed)."""
    from httpx import AsyncClient, ASGITransport
    from clincore.api.main import app
    
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


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
                    "SELECT id, name FROM tenants "
                    "WHERE name IN ('tenant_a', 'tenant_b') ORDER BY name"
                )
            )
        ).fetchall()

    ids_by_name = {name: tid for tid, name in rows}
    tenant_a_id = str(ids_by_name["tenant_a"])
    tenant_b_id = str(ids_by_name["tenant_b"])

    yield tenant_a_id, tenant_b_id

    async with admin_engine.begin() as conn:
        await conn.execute(
            text("DELETE FROM tenants WHERE id IN (:a, :b)"),
            {"a": tenant_a_id, "b": tenant_b_id}
        )


@pytest.fixture
async def tenant_api_key(admin_engine, tenants):
    t1, t2 = tenants
    raw_key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    async with admin_engine.begin() as conn:
        await conn.execute(
            text("""INSERT INTO api_keys (id, tenant_id, key_hash, role, is_active)
                    VALUES (gen_random_uuid(), :tid, :hash, 'user', true)"""),
            {"tid": t1, "hash": key_hash}
        )

    yield raw_key, t1

    async with admin_engine.begin() as conn:
        await conn.execute(
            text("DELETE FROM api_keys WHERE key_hash = :hash"),
            {"hash": key_hash}
        )


@pytest.fixture
async def seed_patients(app_engine, tenants):
    tenant_a, tenant_b = tenants

    async with app_engine.begin() as conn:
        await conn.execute(text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": tenant_a})
        await conn.execute(text("DELETE FROM patients WHERE full_name = 'Alice A'"))
        await conn.execute(text("""
            INSERT INTO patients (id, tenant_id, full_name, patient_no, created_at)
            VALUES (gen_random_uuid(), :tid, 'Alice A', 1, now())
        """), {"tid": tenant_a})

    async with app_engine.begin() as conn:
        await conn.execute(text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": tenant_b})
        await conn.execute(text("DELETE FROM patients WHERE full_name = 'Bob B'"))
        await conn.execute(text("""
            INSERT INTO patients (id, tenant_id, full_name, patient_no, created_at)
            VALUES (gen_random_uuid(), :tid, 'Bob B', 1, now())
        """), {"tid": tenant_b})

    return tenant_a, tenant_b
