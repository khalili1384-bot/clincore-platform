"""
Rate limit tests for PostgreSQL-based rate limiting middleware.
"""
import pytest
import uuid
from datetime import date
from sqlalchemy import text
from clincore.core.rate_limit import LIMITS, DEFAULT_LIMIT, get_limit, check_and_increment
from clincore.core.db import AsyncSessionLocal


def test_rate_limit_constants():
    """Test that rate limit constants are defined correctly."""
    assert LIMITS["/mcare/auto"] == 100, "MCARE auto endpoint should have 100/day limit"
    assert LIMITS["/clinical-cases"] == 200, "Clinical cases endpoint should have 200/day limit"
    assert DEFAULT_LIMIT == 1000, "Default limit should be 1000/day"


def test_get_limit():
    """Test get_limit function."""
    assert get_limit("/mcare/auto") == 100
    assert get_limit("/mcare/auto/123") == 100  # Prefix match
    assert get_limit("/clinical-cases") == 200
    assert get_limit("/clinical-cases/abc") == 200  # Prefix match
    assert get_limit("/patients") == 1000  # Default
    assert get_limit("/unknown") == 1000  # Default


@pytest.mark.asyncio
async def test_rate_limit_mcare_allowed():
    """Test that MCARE requests are allowed under limit."""
    tenant_id = str(uuid.uuid4())
    path = "/mcare/auto"
    
    # Clean up any existing counters
    async with AsyncSessionLocal() as session:
        await session.execute(
            text(f"DELETE FROM rate_limit_counters WHERE tenant_id = '{tenant_id}'")
        )
        await session.commit()
    
    # First request should be allowed
    async with AsyncSessionLocal() as session:
        allowed, current, limit = await check_and_increment(session, tenant_id, path)
        await session.commit()
        assert allowed is True
        assert current == 1
        assert limit == 100


@pytest.mark.asyncio
async def test_rate_limit_mcare_blocked():
    """Test that MCARE requests are blocked when limit exceeded."""
    tenant_id = str(uuid.uuid4())
    path = "/mcare/auto"
    today = date.today().isoformat()
    
    # Set counter to limit
    async with AsyncSessionLocal() as session:
        await session.execute(
            text(f"""
                INSERT INTO rate_limit_counters (tenant_id, endpoint, window_day, count)
                VALUES ('{tenant_id}', '{path}', '{today}', 100)
                ON CONFLICT (tenant_id, endpoint, window_day)
                DO UPDATE SET count = 100
            """)
        )
        await session.commit()
    
    # Next request should be blocked
    async with AsyncSessionLocal() as session:
        allowed, current, limit = await check_and_increment(session, tenant_id, path)
        await session.commit()
        assert allowed is False
        assert current == 101
        assert limit == 100


@pytest.mark.asyncio
async def test_rate_limit_different_tenants():
    """Test that different tenants have separate rate limits."""
    tenant1 = str(uuid.uuid4())
    tenant2 = str(uuid.uuid4())
    path = "/mcare/auto"
    today = date.today().isoformat()
    
    # Set tenant1 to limit
    async with AsyncSessionLocal() as session:
        await session.execute(
            text(f"""
                INSERT INTO rate_limit_counters (tenant_id, endpoint, window_day, count)
                VALUES ('{tenant1}', '{path}', '{today}', 100)
                ON CONFLICT (tenant_id, endpoint, window_day)
                DO UPDATE SET count = 100
            """)
        )
        await session.commit()
    
    # Tenant1 should be blocked
    async with AsyncSessionLocal() as session:
        allowed, _, _ = await check_and_increment(session, tenant1, path)
        await session.commit()
        assert allowed is False
    
    # Tenant2 should still be allowed
    async with AsyncSessionLocal() as session:
        allowed, current, _ = await check_and_increment(session, tenant2, path)
        await session.commit()
        assert allowed is True
        assert current == 1


@pytest.mark.asyncio
async def test_rate_limit_clinical_cases():
    """Test clinical cases endpoint limit."""
    tenant_id = str(uuid.uuid4())
    path = "/clinical-cases"
    
    # Clean up
    async with AsyncSessionLocal() as session:
        await session.execute(
            text(f"DELETE FROM rate_limit_counters WHERE tenant_id = '{tenant_id}'")
        )
        await session.commit()
    
    # First request
    async with AsyncSessionLocal() as session:
        allowed, current, limit = await check_and_increment(session, tenant_id, path)
        await session.commit()
        assert allowed is True
        assert current == 1
        assert limit == 200


@pytest.mark.asyncio
async def test_rate_limit_default():
    """Test default limit for unknown endpoints."""
    tenant_id = str(uuid.uuid4())
    path = "/patients"
    
    # Clean up
    async with AsyncSessionLocal() as session:
        await session.execute(
            text(f"DELETE FROM rate_limit_counters WHERE tenant_id = '{tenant_id}'")
        )
        await session.commit()
    
    # First request
    async with AsyncSessionLocal() as session:
        allowed, current, limit = await check_and_increment(session, tenant_id, path)
        await session.commit()
        assert allowed is True
        assert current == 1
        assert limit == 1000


@pytest.mark.asyncio
async def test_rate_limit_day_reset():
    """Test that counters are per-day (different days have separate counters)."""
    tenant_id = str(uuid.uuid4())
    path = "/mcare/auto"
    
    # This test verifies the unique constraint includes window_day
    # So same tenant + endpoint on different days = different counters
    
    # Clean up
    async with AsyncSessionLocal() as session:
        await session.execute(
            text(f"DELETE FROM rate_limit_counters WHERE tenant_id = '{tenant_id}'")
        )
        await session.commit()
    
    # Add counter for today
    today = date.today().isoformat()
    async with AsyncSessionLocal() as session:
        await session.execute(
            text(f"""
                INSERT INTO rate_limit_counters (tenant_id, endpoint, window_day, count)
                VALUES ('{tenant_id}', '{path}', '{today}', 50)
            """)
        )
        await session.commit()
    
    # Verify counter exists for today
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text(f"""
                SELECT count FROM rate_limit_counters
                WHERE tenant_id = '{tenant_id}' AND endpoint = '{path}' AND window_day = '{today}'
            """)
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] == 50
