# ───────────────────────────────────────────────────────
# ClinCore Platform — Proprietary & Confidential
# Copyright © 2026 ClinCore
# All rights reserved. Unauthorized use strictly prohibited.
# ───────────────────────────────────────────────────────
"""
Rate limiting using PostgreSQL counters.
Window: UTC calendar day (reset at 00:00 UTC).
"""
from datetime import date
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import Table, Column, BigInteger, String, Date, Integer, MetaData
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, insert as pg_insert

LIMITS = {
    "/mcare/auto": 100,
    "/clinical-cases": 200,
}
DEFAULT_LIMIT = 1000


def get_limit(path: str) -> int:
    """Get rate limit for a given endpoint path."""
    for prefix, limit in LIMITS.items():
        if path.startswith(prefix):
            return limit
    return DEFAULT_LIMIT


# Define table structure for SQLAlchemy Core operations
_meta = MetaData()
_rl_table = Table(
    "rate_limit_counters",
    _meta,
    Column("id", BigInteger, primary_key=True),
    Column("tenant_id", PG_UUID(as_uuid=True)),
    Column("endpoint", String(120)),
    Column("window_day", Date),
    Column("count", Integer),
)


async def check_and_increment(
    session: AsyncSession,
    tenant_id: str,
    path: str,
) -> tuple[bool, int, int]:
    """
    Check rate limit and increment counter atomically.
    
    Returns: (allowed: bool, current_count: int, limit: int)
    
    Uses INSERT ... ON CONFLICT DO UPDATE (upsert) — atomic, no race condition.
    """
    limit = get_limit(path)
    today = date.today()
    
    # Convert tenant_id string to UUID
    try:
        tenant_uuid = UUID(tenant_id)
    except (ValueError, AttributeError):
        # Invalid UUID, allow request (fail open)
        return True, 0, limit

    # Atomic upsert using SQLAlchemy Core (driver-agnostic)
    stmt = (
        pg_insert(_rl_table)
        .values(tenant_id=tenant_uuid, endpoint=path, window_day=today, count=1)
        .on_conflict_do_update(
            constraint="uq_rl_tenant_endpoint_day",
            set_={"count": _rl_table.c.count + 1},
        )
        .returning(_rl_table.c.count)
    )
    
    result = await session.execute(stmt)
    row = result.fetchone()
    current = row[0] if row else 1
    
    # Note: Caller is responsible for committing the session
    # This allows the function to be used within larger transactions

    allowed = current <= limit
    return allowed, current, limit
