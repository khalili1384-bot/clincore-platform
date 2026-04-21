from fastapi import APIRouter, Request, Query, HTTPException
from sqlalchemy import text
from clincore.core.db import tenant_session

router = APIRouter(prefix="/encounters", tags=["encounters"])


@router.get("/")
async def list_encounters(request: Request, patient_id: str = Query(None)):
    tenant_id = request.headers.get("X-Tenant-Id", "")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-Id required")
    async with tenant_session(tenant_id) as session:
        if patient_id:
            result = await session.execute(
                text("SELECT id, tenant_id, patient_id, occurred_at, chief_complaint, created_at FROM encounters WHERE patient_id = :pid ORDER BY occurred_at DESC"),
                {"pid": patient_id}
            )
        else:
            result = await session.execute(
                text("SELECT id, tenant_id, patient_id, occurred_at, chief_complaint, created_at FROM encounters ORDER BY occurred_at DESC")
            )
        rows = result.fetchall()
        return {"encounters": [{"id": str(r[0]), "tenant_id": str(r[1]), "patient_id": str(r[2]), "occurred_at": str(r[3]), "chief_complaint": r[4], "created_at": str(r[5])} for r in rows], "total": len(rows)}


@router.post("/")
async def create_encounter(request: Request):
    payload = await request.json()
    tenant_id = request.headers.get("X-Tenant-Id", "")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-Id required")
    patient_id = (payload.get("patient_id") or "").strip()
    chief_complaint = (payload.get("chief_complaint") or "").strip()
    occurred_at = (payload.get("occurred_at") or "").strip()
    if not patient_id or not chief_complaint:
        raise HTTPException(status_code=422, detail="patient_id and chief_complaint are required")
    async with tenant_session(tenant_id) as session:
        if occurred_at:
            result = await session.execute(
                text("INSERT INTO encounters (id, tenant_id, patient_id, occurred_at, chief_complaint, created_at) VALUES (gen_random_uuid(), :tid, :pid, :oat, :cc, now()) RETURNING id, tenant_id, patient_id, occurred_at, chief_complaint, created_at"),
                {"tid": tenant_id, "pid": patient_id, "oat": occurred_at, "cc": chief_complaint}
            )
        else:
            result = await session.execute(
                text("INSERT INTO encounters (id, tenant_id, patient_id, occurred_at, chief_complaint, created_at) VALUES (gen_random_uuid(), :tid, :pid, now(), :cc, now()) RETURNING id, tenant_id, patient_id, occurred_at, chief_complaint, created_at"),
                {"tid": tenant_id, "pid": patient_id, "cc": chief_complaint}
            )
        await session.commit()
        row = result.fetchone()
        return {"id": str(row[0]), "tenant_id": str(row[1]), "patient_id": str(row[2]), "occurred_at": str(row[3]), "chief_complaint": row[4], "created_at": str(row[5])}


@router.get("/{encounter_id}")
async def get_encounter(request: Request, encounter_id: str):
    tenant_id = request.headers.get("X-Tenant-Id", "")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-Id required")
    async with tenant_session(tenant_id) as session:
        result = await session.execute(
            text("SELECT id, tenant_id, patient_id, occurred_at, chief_complaint, created_at FROM encounters WHERE id = :eid"),
            {"eid": encounter_id}
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Encounter not found")
        return {"id": str(row[0]), "tenant_id": str(row[1]), "patient_id": str(row[2]), "occurred_at": str(row[3]), "chief_complaint": row[4], "created_at": str(row[5])}
