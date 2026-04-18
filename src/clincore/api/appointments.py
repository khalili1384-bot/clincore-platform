"""
Appointments API endpoints.
Requires X-Tenant-Id header (set by middleware).
"""
import os
import asyncio
import urllib.parse
import psycopg
from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import text
from clincore.core.db import tenant_session

router = APIRouter(prefix="/appointments", tags=["appointments"])

_raw = os.getenv("DATABASE_URL", "")
if _raw:
    PSYCOPG_URL = _raw.replace("postgresql+psycopg://", "postgresql://").replace("postgresql+asyncpg://", "postgresql://").replace("postgresql+psycopg_async://", "postgresql://")
else:
    _pw = urllib.parse.quote_plus(os.getenv("DB_PASSWORD", ""))
    PSYCOPG_URL = (
        f"postgresql://{os.getenv('DB_USER','clincore_user')}:{_pw}"
        f"@{os.getenv('DB_HOST','127.0.0.1')}:"
        f"{os.getenv('DB_PORT','5432')}/{os.getenv('DB_NAME','clincore')}"
    )


@router.get("/")
async def list_appointments(request: Request, patient_id: str = Query(None)):
    """List appointments, optionally filtered by patient_id."""
    tenant_id = request.headers.get("X-Tenant-Id", "")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-Id required")
    
    async with tenant_session(tenant_id) as session:
        if patient_id:
            query = f"SELECT id, tenant_id, patient_id, scheduled_for, status, notes, created_at FROM appointments WHERE patient_id = '{patient_id}' AND tenant_id = '{tenant_id}' ORDER BY scheduled_for DESC"
        else:
            query = f"SELECT id, tenant_id, patient_id, scheduled_for, status, notes, created_at FROM appointments WHERE tenant_id = '{tenant_id}' ORDER BY scheduled_for DESC"
        
        result = await session.execute(text(query))
        rows = result.fetchall()
        appointments = [
            {
                "id": str(r[0]),
                "tenant_id": str(r[1]),
                "patient_id": str(r[2]),
                "scheduled_for": str(r[3]),
                "status": r[4],
                "notes": r[5],
                "created_at": str(r[6]),
            }
            for r in rows
        ]
        return {"appointments": appointments, "total": len(appointments)}


@router.post("/")
async def create_appointment(request: Request):
    """Create an appointment."""
    payload = await request.json()
    tenant_id = request.headers.get("X-Tenant-Id", "")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-Id required")
    
    patient_id = (payload.get("patient_id") or "").strip()
    scheduled_for = (payload.get("scheduled_for") or "").strip()
    status = (payload.get("status") or "scheduled").strip()
    notes = (payload.get("notes") or "").strip()
    
    if not patient_id or not scheduled_for:
        raise HTTPException(status_code=422, detail="patient_id and scheduled_for are required")
    
    notes_val = f"'{notes}'" if notes else "NULL"
    
    async with tenant_session(tenant_id) as session:
        result = await session.execute(
            text(f"INSERT INTO appointments (id, tenant_id, patient_id, scheduled_for, status, notes, created_at) VALUES (gen_random_uuid(), '{tenant_id}', '{patient_id}', '{scheduled_for}', '{status}', {notes_val}, now()) RETURNING id, tenant_id, patient_id, scheduled_for, status, notes, created_at")
        )
        await session.commit()
        row = result.fetchone()
        return {"id": str(row[0]), "tenant_id": str(row[1]), "patient_id": str(row[2]), "scheduled_for": str(row[3]), "status": row[4], "notes": row[5], "created_at": str(row[6])}
