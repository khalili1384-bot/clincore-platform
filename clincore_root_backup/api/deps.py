from __future__ import annotations

from typing import AsyncIterator

from fastapi import Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import tenant_session_scope


async def get_tenant_session(
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> AsyncIterator[AsyncSession]:
    """
    Enforces fail-closed: no tenant header => no DB access.
    """
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="Missing X-Tenant-Id header")

    async with tenant_session_scope(x_tenant_id) as session:
        yield session
