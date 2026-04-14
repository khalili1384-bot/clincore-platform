from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from app.core.config import settings

TENANT_GUC = "app.tenant_id"

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=False,
)


async def _set_tenant_context(conn: AsyncConnection, tenant_id: UUID) -> None:
    await conn.execute(text(f"SELECT set_config('{TENANT_GUC}', :tid, true)"), {"tid": str(tenant_id)})


async def in_tenant_tx(
    tenant_id: UUID,
    fn: Callable[[AsyncConnection], Awaitable[object]],
    engine_override: AsyncEngine | None = None,
) -> object:
    _engine = engine_override or engine
    async with _engine.begin() as conn:
        await _set_tenant_context(conn, tenant_id)
        return await fn(conn)
