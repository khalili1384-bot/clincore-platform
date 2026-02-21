from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy import text
from clincore.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionFactory = async_sessionmaker(
    engine,
    expire_on_commit=False,
)


@asynccontextmanager
async def tenant_session(tenant_id: str):
    """
    Dedicated connection + transaction + SET LOCAL.
    No pool leakage possible.
    """
    async with engine.connect() as conn:
        async with conn.begin():
            await conn.execute(
                text("SET LOCAL app.tenant_id = :tid"),
                {"tid": str(tenant_id)},
            )
            session = AsyncSession(bind=conn, expire_on_commit=False)
            yield session