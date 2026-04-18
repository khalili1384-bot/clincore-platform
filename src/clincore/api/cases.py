"""
Clinical Cases API endpoints.
Requires X-Tenant-Id header (set by middleware).
"""
import os
import asyncio
import urllib.parse
import psycopg
from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/clinical-cases", tags=["clinical-cases"])

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
async def list_cases(request: Request, patient_id: str = Query(None), status: str = Query(None)):
    """List cases, optionally filtered by patient_id or status."""
    tenant_id = request.state.tenant_id
    
    def query_db():
        with psycopg.connect(PSYCOPG_URL) as conn:
            with conn.cursor() as cur:
                query = "SELECT id, patient_id, status, created_at FROM cases"
                conditions = []
                
                if patient_id:
                    conditions.append(f"patient_id = '{patient_id}'")
                if status:
                    conditions.append(f"status = '{status}'")
                
                conditions.append(f"tenant_id = '{tenant_id}'")
                query += " WHERE " + " AND ".join(conditions)
                
                query += " ORDER BY created_at DESC"
                
                cur.execute(query)
                rows = cur.fetchall()
                cases = [
                    {
                        "id": str(row[0]),
                        "patient_id": str(row[1]),
                        "status": row[2],
                        "created_at": row[3].isoformat() if row[3] else None,
                    }
                    for row in rows
                ]
                return cases
    
    cases = await asyncio.to_thread(query_db)
    return {"ok": True, "cases": cases}


@router.get("/{case_id}")
async def get_case(request: Request, case_id: str):
    """Get single case with case_results."""
    tenant_id = request.state.tenant_id
    
    def query_db():
        with psycopg.connect(PSYCOPG_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT id, patient_id, status, created_at FROM cases WHERE id = '{case_id}' AND tenant_id = '{tenant_id}'"
                )
                row = cur.fetchone()
                
                if not row:
                    return None
                
                # Get case results
                cur.execute(
                    f"SELECT id, result_type, result_data, created_at FROM case_results WHERE case_id = '{case_id}' ORDER BY created_at"
                )
                results_rows = cur.fetchall()
                case_results = [
                    {
                        "id": str(r[0]),
                        "result_type": r[1],
                        "result_data": r[2],
                        "created_at": r[3].isoformat() if r[3] else None,
                    }
                    for r in results_rows
                ]
                
                return {
                    "id": str(row[0]),
                    "patient_id": str(row[1]),
                    "status": row[2],
                    "created_at": row[3].isoformat() if row[3] else None,
                    "case_results": case_results,
                }
    
    result = await asyncio.to_thread(query_db)
    
    if not result:
        return JSONResponse(status_code=404, content={"error": "Case not found"})
    
    return {"ok": True, **result}
