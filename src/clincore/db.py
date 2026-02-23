from __future__ import annotations

import sys
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .config import get_settings


# ─────────────────────────────────────────
# Windows Event Loop Fix (psycopg3 async)
# ─────────────────────────────────────────

def _fix_windows_event_loop() -> None:
    """
    Psycopg async on Windows is not compatible with ProactorEventLoop.
    Force SelectorEventLoop.
    """
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(
            asyncio.WindowsSelectorEventLoopPolicy()
        )


_fix_windows_event_loop()


# ─────────────────────────────────────────
# Engine & Session Factory
# ─────────────────────────────────────────

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
)


# ─────────────────────────────────────────
# Generic Session (NO tenant context)
# ─────────────────────────────────────────

@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """
    Generic DB session scope.
    Use ONLY for non-tenant tables (e.g., tenants).
    """
    async with SessionLocal() as session:
        async with session.begin():
            yield session


# ─────────────────────────────────────────
# Tenant-Aware Session (RLS Safe)
# ─────────────────────────────────────────

@asynccontextmanager
async def tenant_session(tenant_id: str) -> AsyncIterator[AsyncSession]:
    """
    Production-safe tenant-aware session.

    Guarantees:
    - Explicit transaction boundary
    - SET LOCAL inside transaction
    - No bind parameters (avoid psycopg $1 bug)
    - Auto-reset after transaction ends
    - Fail-closed if tenant_id missing
    """

    if not tenant_id:
        raise ValueError("tenant_id is required (fail-closed)")

    async with SessionLocal() as session:
        async with session.begin():

            # IMPORTANT:
            # SET LOCAL cannot use bind parameters in psycopg3.
            # Inline value explicitly.
            await session.execute(
                text(f"SET LOCAL app.tenant_id = '{tenant_id}'")
            )

            yield session