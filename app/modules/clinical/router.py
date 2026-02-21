from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Header, HTTPException

from app.core.shared.db import in_tenant_tx
from app.modules.clinical.repositories import SqlPatientRepo
from app.modules.clinical.schemas import PatientCreateIn, PatientOut

router = APIRouter(tags=["clinical-lite"])
patient_repo = SqlPatientRepo()


def _tenant_from_header(x_tenant_id: str | None) -> UUID:
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="Missing X-Tenant-Id header")
    try:
        return UUID(x_tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid X-Tenant-Id") from e


@router.post("/patients", response_model=PatientOut)
async def create_patient(
    payload: PatientCreateIn,
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
):
    tenant_id = _tenant_from_header(x_tenant_id)

    async def _fn(conn):
        return await patient_repo.create(conn, tenant_id=tenant_id, full_name=payload.full_name)

    dto = await in_tenant_tx(tenant_id, _fn)
    return PatientOut(id=dto.id, full_name=dto.full_name, created_at=dto.created_at)


@router.get("/patients", response_model=list[PatientOut])
async def list_patients(x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id")):
    tenant_id = _tenant_from_header(x_tenant_id)

    async def _fn(conn):
        return await patient_repo.list(conn, limit=50)

    dtos = await in_tenant_tx(tenant_id, _fn)
    return [PatientOut(id=d.id, full_name=d.full_name, created_at=d.created_at) for d in dtos]
