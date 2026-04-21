from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import text
from clincore.core.db import tenant_session

router = APIRouter(prefix="/clinical-cases", tags=["clinical-cases"])


@router.get("/")
async def list_cases(request: Request, patient_id: str = Query(None), status: str = Query(None)):
    tenant_id = request.headers.get("X-Tenant-Id", "")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-Id required")
    async with tenant_session(tenant_id) as session:
        if patient_id and status:
            result = await session.execute(
                text("SELECT id, patient_id, status, created_at FROM cases WHERE patient_id = :pid AND status = :st ORDER BY created_at DESC"),
                {"pid": patient_id, "st": status}
            )
        elif patient_id:
            result = await session.execute(
                text("SELECT id, patient_id, status, created_at FROM cases WHERE patient_id = :pid ORDER BY created_at DESC"),
                {"pid": patient_id}
            )
        elif status:
            result = await session.execute(
                text("SELECT id, patient_id, status, created_at FROM cases WHERE status = :st ORDER BY created_at DESC"),
                {"st": status}
            )
        else:
            result = await session.execute(
                text("SELECT id, patient_id, status, created_at FROM cases ORDER BY created_at DESC")
            )
        rows = result.fetchall()
        return {"ok": True, "cases": [{"id": str(r[0]), "patient_id": str(r[1]), "status": r[2], "created_at": str(r[3])} for r in rows]}


@router.get("/{case_id}")
async def get_case(request: Request, case_id: str):
    tenant_id = request.headers.get("X-Tenant-Id", "")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-Id required")
    async with tenant_session(tenant_id) as session:
        result = await session.execute(
            text("SELECT id, patient_id, status, created_at FROM cases WHERE id = :cid"),
            {"cid": case_id}
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Case not found")
        res = await session.execute(
            text("SELECT id, rank, remedy_name, mcare_score, coverage FROM case_results WHERE case_id = :cid ORDER BY rank"),
            {"cid": case_id}
        )
        results = [{"id": str(r[0]), "rank": r[1], "remedy_name": r[2], "mcare_score": r[3], "coverage": r[4]} for r in res.fetchall()]
        return {"ok": True, "id": str(row[0]), "patient_id": str(row[1]), "status": row[2], "created_at": str(row[3]), "case_results": results}
