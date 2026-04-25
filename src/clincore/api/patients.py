from fastapi import APIRouter, Request, HTTPException
from sqlalchemy import text
from clincore.core.db import tenant_session

router = APIRouter(tags=["patients"])

def _fmt(n) -> str:
    return f"P-{int(n):04d}"

@router.get("/patients")
async def list_patients(request: Request):
    tenant_id = request.headers.get("X-Tenant-Id", "")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-Id required")
    async with tenant_session(tenant_id) as session:
        result = await session.execute(
            text("SELECT id, tenant_id, full_name, patient_no, created_at FROM patients ORDER BY patient_no ASC")
        )
        rows = result.fetchall()
        return {"patients": [{"id": str(r[0]), "tenant_id": str(r[1]), "full_name": r[2], "patient_no": _fmt(r[3]), "created_at": str(r[4])} for r in rows], "total": len(rows)}

@router.post("/patients")
async def create_patient(request: Request):
    payload = await request.json()
    full_name = (payload.get("full_name") or "").strip()
    if not full_name:
        raise HTTPException(status_code=422, detail="full_name required")
    tenant_id = request.headers.get("X-Tenant-Id", "")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-Id required")
    async with tenant_session(tenant_id) as session:
        seq = await session.execute(text("SELECT COALESCE(MAX(patient_no), 0) + 1 FROM patients"))
        next_no = seq.scalar()
        result = await session.execute(
            text("INSERT INTO patients (id, tenant_id, full_name, patient_no, created_at) VALUES (gen_random_uuid(), :tid, :name, :pno, now()) RETURNING id, tenant_id, full_name, patient_no, created_at"),
            {"tid": tenant_id, "name": full_name, "pno": next_no}
        )
        await session.commit()
        row = result.fetchone()
        return {"id": str(row[0]), "tenant_id": str(row[1]), "full_name": row[2], "patient_no": _fmt(row[3]), "created_at": str(row[4])}

@router.get("/patients/{patient_id}")
async def get_patient(request: Request, patient_id: str):
    tenant_id = request.headers.get("X-Tenant-Id", "")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-Id required")
    async with tenant_session(tenant_id) as session:
        result = await session.execute(
            text("SELECT id, full_name, patient_no, created_at FROM patients WHERE id = :pid"),
            {"pid": patient_id}
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Patient not found")
        return {"ok": True, "id": str(row[0]), "full_name": row[1], "patient_no": _fmt(row[2]), "created_at": str(row[3])}