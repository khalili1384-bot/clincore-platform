from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from app.core.config import settings

TENANT_GUC = "app.tenant_id"


engine: AsyncEngine = create_async_engine(settings.database_url, pool_pre_ping=True)


async def _set_tenant_context(conn: AsyncConnection, tenant_id: UUID) -> None:
    # FIRST statement in the transaction (architecture invariant)
    await conn.execute(text("SELECT set_config(:k, :v, true)"), {"k": TENANT_GUC, "v": str(tenant_id)})


async def in_tenant_tx(
    tenant_id: UUID,
    fn: Callable[[AsyncConnection], Awaitable[object]],
) -> object:
    async with engine.begin() as conn:
        await _set_tenant_context(conn, tenant_id)
        return await fn(conn)
