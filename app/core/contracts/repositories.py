from __future__ import annotations

from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.contracts.dtos import PatientDTO


class PatientRepo(Protocol):
    async def create(self, conn: AsyncConnection, *, tenant_id: UUID, full_name: str) -> PatientDTO: ...
    async def list(self, conn: AsyncConnection, *, limit: int = 50) -> list[PatientDTO]: ...
