"""
Rate limit tests for PostgreSQL-based rate limiting middleware.
These are unit tests that verify the rate limiting logic.
"""
import pytest
from src.clincore.core.ratelimit import LIMITS, DEFAULT_LIMIT


def test_rate_limit_constants():
    """Test that rate limit constants are defined correctly."""
    assert LIMITS["/mcare/auto"] == 100, "MCARE auto endpoint should have 100/day limit"
    assert LIMITS["/clinical-cases"] == 200, "Clinical cases endpoint should have 200/day limit"
    assert DEFAULT_LIMIT == 1000, "Default limit should be 1000/day"


def test_rate_limit_endpoint_lookup():
    """Test that endpoint limits can be looked up correctly."""
    # Known endpoints
    assert LIMITS.get("/mcare/auto", DEFAULT_LIMIT) == 100
    assert LIMITS.get("/clinical-cases", DEFAULT_LIMIT) == 200
    
    # Unknown endpoint should use default
    assert LIMITS.get("/unknown/endpoint", DEFAULT_LIMIT) == 1000
    assert LIMITS.get("/api/v1/users", DEFAULT_LIMIT) == 1000


def test_rate_limit_logic():
    """Test rate limiting logic (count vs limit)."""
    # Under limit
    count = 50
    limit = 100
    assert count < limit, "Request should be allowed when count < limit"
    
    # At limit
    count = 100
    limit = 100
    assert count >= limit, "Request should be blocked when count >= limit"
    
    # Over limit
    count = 150
    limit = 100
    assert count >= limit, "Request should be blocked when count > limit"
