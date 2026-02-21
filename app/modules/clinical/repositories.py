from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.contracts.dtos import PatientDTO
from app.core.contracts.repositories import PatientRepo
from app.modules.clinical.db import models


class SqlPatientRepo(PatientRepo):
    async def create(self, conn: AsyncConnection, *, tenant_id: UUID, full_name: str) -> PatientDTO:
        stmt = (
            insert(models.Patient)
            .values(id=uuid4(), tenant_id=tenant_id, full_name=full_name)
            .returning(models.Patient.id, models.Patient.full_name, models.Patient.created_at)
        )
        res = await conn.execute(stmt)
        row = res.one()
        return PatientDTO(id=row.id, full_name=row.full_name, created_at=row.created_at)

    async def list(self, conn: AsyncConnection, *, limit: int = 50) -> list[PatientDTO]:
        stmt = (
            select(models.Patient.id, models.Patient.full_name, models.Patient.created_at)
            .order_by(models.Patient.created_at.desc())
            .limit(limit)
        )
        res = await conn.execute(stmt)
        return [PatientDTO(id=r.id, full_name=r.full_name, created_at=r.created_at) for r in res]
