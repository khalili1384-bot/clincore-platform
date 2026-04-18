"""
Patients API endpoints.
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

router = APIRouter(tags=["patients"])

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


@router.get("/patients")
async def list_patients(request: Request):
    """List all patients for tenant."""
    tenant_id = request.headers.get("X-Tenant-Id", "")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-Id required")
    async with tenant_session(tenant_id) as session:
        result = await session.execute(
            text(f"SELECT id, tenant_id, full_name, created_at FROM patients WHERE tenant_id = '{tenant_id}' ORDER BY created_at DESC")
        )
        rows = result.fetchall()
        patients = [{"id": str(r[0]), "tenant_id": str(r[1]), "full_name": r[2], "created_at": str(r[3])} for r in rows]
        return {"patients": patients, "total": len(patients)}


@router.post("/patients")
async def create_patient(request: Request):
    """Create a patient."""
    payload = await request.json()
    full_name = (payload.get("full_name") or "").strip()
    if not full_name:
        raise HTTPException(status_code=422, detail="full_name required")
    
    tenant_id = request.headers.get("X-Tenant-Id", "")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-Id required")
    
    async with tenant_session(tenant_id) as session:
        result = await session.execute(
            text(f"INSERT INTO patients (id, tenant_id, full_name, created_at) VALUES (gen_random_uuid(), '{tenant_id}', '{full_name}', now()) RETURNING id, tenant_id, full_name, created_at")
        )
        await session.commit()
        row = result.fetchone()
        return {"id": str(row[0]), "tenant_id": str(row[1]), "full_name": row[2], "created_at": str(row[3])}


@router.get("/patients/{patient_id}")
async def get_patient(request: Request, patient_id: str):
    """Get single patient by ID."""
    tenant_id = request.state.tenant_id
    
    def query_db():
        with psycopg.connect(PSYCOPG_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT id, full_name, created_at FROM patients WHERE id = '{patient_id}' AND tenant_id = '{tenant_id}'"
                )
                row = cur.fetchone()
                
                if not row:
                    return None
                
                return {
                    "id": str(row[0]),
                    "full_name": row[1],
                    "created_at": row[2].isoformat() if row[2] else None,
                }
    
    result = await asyncio.to_thread(query_db)
    
    if not result:
        return JSONResponse(status_code=404, content={"error": "Patient not found"})
    
    return {"ok": True, **result}
