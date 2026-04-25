from datetime import datetime
from fastapi import APIRouter, Request, Query, HTTPException
from sqlalchemy import text
from clincore.core.db import tenant_session

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.get("/")
async def list_appointments(request: Request, patient_id: str = Query(None)):
    tenant_id = request.headers.get("X-Tenant-Id", "")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-Id required")
    async with tenant_session(tenant_id) as session:
        if patient_id:
            result = await session.execute(
                text("SELECT id, tenant_id, patient_id, scheduled_for, status, notes, created_at FROM appointments WHERE patient_id = :pid ORDER BY scheduled_for DESC"),
                {"pid": patient_id}
            )
        else:
            result = await session.execute(
                text("SELECT id, tenant_id, patient_id, scheduled_for, status, notes, created_at FROM appointments ORDER BY scheduled_for DESC")
            )
        rows = result.fetchall()
        return {"appointments": [{"id": str(r[0]), "tenant_id": str(r[1]), "patient_id": str(r[2]), "scheduled_for": str(r[3]), "status": r[4], "notes": r[5], "created_at": str(r[6])} for r in rows], "total": len(rows)}


@router.post("/")
async def create_appointment(request: Request):
    payload = await request.json()
    tenant_id = request.headers.get("X-Tenant-Id", "")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-Id required")
    patient_id = (payload.get("patient_id") or "").strip()
    scheduled_for_str = (payload.get("scheduled_for") or "").strip()
    status = (payload.get("status") or "scheduled").strip()
    notes = (payload.get("notes") or None)
    if not patient_id or not scheduled_for_str:
        raise HTTPException(status_code=422, detail="patient_id and scheduled_for are required")
    try:
        scheduled_for = datetime.fromisoformat(scheduled_for_str.replace(' ', 'T'))
    except ValueError:
        raise HTTPException(status_code=422, detail="scheduled_for must be a valid datetime")
    async with tenant_session(tenant_id) as session:
        result = await session.execute(
            text("INSERT INTO appointments (id, tenant_id, patient_id, scheduled_for, status, notes, created_at) VALUES (gen_random_uuid(), :tid, :pid, :sf, :st, :notes, now()) RETURNING id, tenant_id, patient_id, scheduled_for, status, notes, created_at"),
            {"tid": tenant_id, "pid": patient_id, "sf": scheduled_for, "st": status, "notes": notes}
        )
        await session.commit()
        row = result.fetchone()
        return {"id": str(row[0]), "tenant_id": str(row[1]), "patient_id": str(row[2]), "scheduled_for": str(row[3]), "status": row[4], "notes": row[5], "created_at": str(row[6])}
