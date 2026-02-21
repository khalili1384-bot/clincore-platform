from __future__ import annotations

import sys
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .config import get_settings


def _fix_windows_event_loop() -> None:
    """
    Psycopg async on Windows is not compatible with ProactorEventLoop.
    This makes it work reliably.
    """
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


_fix_windows_event_loop()

settings = get_settings()

engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """
    Generic DB session scope (NO tenant context here).
    Useful for non-tenant tables only (e.g., tenants table if you want).
    """
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def tenant_session_scope(tenant_id: str) -> AsyncIterator[AsyncSession]:
    """
    Tenant-aware session scope.

    - Starts an explicit transaction.
    - Sets `SET LOCAL app.tenant_id = <tenant_id>` for RLS policies.
    - Fail-closed behavior happens naturally: if tenant_id is missing/None -> your code should not call this.
    """
    if not tenant_id:
        raise ValueError("tenant_id is required (fail-closed)")

    async with SessionLocal() as session:
        try:
            # Begin a transaction so SET LOCAL applies properly.
            await session.execute(text("BEGIN"))
            await session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tenant_id})

            yield session

            await session.commit()
        except Exception:
            await session.rollback()
            raise
