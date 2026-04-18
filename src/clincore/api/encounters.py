"""
Encounters API endpoints.
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

router = APIRouter(prefix="/encounters", tags=["encounters"])

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
async def list_encounters(request: Request, patient_id: str = Query(None)):
    """List encounters, optionally filtered by patient_id."""
    tenant_id = request.headers.get("X-Tenant-Id", "")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-Id required")
    
    async with tenant_session(tenant_id) as session:
        if patient_id:
            query = f"SELECT id, tenant_id, patient_id, occurred_at, chief_complaint, created_at FROM encounters WHERE patient_id = '{patient_id}' AND tenant_id = '{tenant_id}' ORDER BY occurred_at DESC"
        else:
            query = f"SELECT id, tenant_id, patient_id, occurred_at, chief_complaint, created_at FROM encounters WHERE tenant_id = '{tenant_id}' ORDER BY occurred_at DESC"
        
        result = await session.execute(text(query))
        rows = result.fetchall()
        encounters = [
            {
                "id": str(r[0]),
                "tenant_id": str(r[1]),
                "patient_id": str(r[2]),
                "occurred_at": str(r[3]),
                "chief_complaint": r[4],
                "created_at": str(r[5]),
            }
            for r in rows
        ]
        return {"encounters": encounters, "total": len(encounters)}


@router.post("/")
async def create_encounter(request: Request):
    """Create an encounter."""
    payload = await request.json()
    tenant_id = request.headers.get("X-Tenant-Id", "")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-Id required")
    
    patient_id = (payload.get("patient_id") or "").strip()
    occurred_at = (payload.get("occurred_at") or "").strip()
    chief_complaint = (payload.get("chief_complaint") or "").strip()
    
    if not patient_id or not chief_complaint:
        raise HTTPException(status_code=422, detail="patient_id and chief_complaint are required")
    
    date_val = f"'{occurred_at}'" if occurred_at else "now()"
    
    async with tenant_session(tenant_id) as session:
        result = await session.execute(
            text(f"INSERT INTO encounters (id, tenant_id, patient_id, occurred_at, chief_complaint, created_at) VALUES (gen_random_uuid(), '{tenant_id}', '{patient_id}', {date_val}, '{chief_complaint}', now()) RETURNING id, tenant_id, patient_id, occurred_at, chief_complaint, created_at")
        )
        await session.commit()
        row = result.fetchone()
        return {"id": str(row[0]), "tenant_id": str(row[1]), "patient_id": str(row[2]), "occurred_at": str(row[3]), "chief_complaint": row[4], "created_at": str(row[5])}


@router.get("/{encounter_id}")
async def get_encounter(request: Request, encounter_id: str):
    """Get single encounter by ID."""
    tenant_id = request.headers.get("X-Tenant-Id", "")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-Id required")
    
    async with tenant_session(tenant_id) as session:
        result = await session.execute(
            text(f"SELECT id, tenant_id, patient_id, occurred_at, chief_complaint, created_at FROM encounters WHERE id = '{encounter_id}' AND tenant_id = '{tenant_id}'")
        )
        row = result.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Encounter not found")
        
        return {
            "id": str(row[0]),
            "tenant_id": str(row[1]),
            "patient_id": str(row[2]),
            "occurred_at": str(row[3]),
            "chief_complaint": row[4],
            "created_at": str(row[5]),
        }
