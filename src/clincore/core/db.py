from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from clincore.core.config import settings

engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=False,
    connect_args={"server_settings": {"jit": "off"}} if "asyncpg" in settings.DATABASE_URL else {},
)

admin_engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=False,
    connect_args={"server_settings": {"jit": "off"}} if "asyncpg" in settings.DATABASE_URL else {},
)

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


@asynccontextmanager
async def tenant_session(tenant_id: str) -> AsyncGenerator[AsyncSession, None]:
    """Create a session with tenant context set."""
    async with AsyncSessionLocal() as session:
        await session.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": tenant_id}
        )
        yield session
