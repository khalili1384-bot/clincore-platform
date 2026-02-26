from __future__ import annotations

import hashlib
import json
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from clincore.db import tenant_session

router = APIRouter(prefix="/cases", tags=["cases"])


class CreateCaseRequest(BaseModel):
    patient_id: uuid.UUID
    input_payload: dict[str, Any]


async def _tenant_db(x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID")):
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="Missing X-Tenant-ID header")

    async with tenant_session(x_tenant_id) as session:
        yield session


@router.post("")
async def create_case(payload: CreateCaseRequest, db: AsyncSession = Depends(_tenant_db)):
    case_id = uuid.uuid4()

    tenant_row = (
        await db.execute(
            text("SELECT NULLIF(current_setting('app.tenant_id', true), '')::uuid AS tenant_id")
        )
    ).mappings().first()

    tenant_id = tenant_row["tenant_id"] if tenant_row else None
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Tenant context is not set")

    await db.execute(
        text(
            """
            INSERT INTO cases (id, tenant_id, input_payload, random_seed, status, created_at)
            VALUES (:id, :tenant_id, CAST(:input_payload AS jsonb), :random_seed, 'draft', now())
            """
        ),
        {
            "id": case_id,
            "tenant_id": tenant_id,
            "input_payload": json.dumps(payload.input_payload),
            "random_seed": "0",
        },
    )

    return {"case_id": case_id, "status": "draft"}


@router.post("/{case_id}/finalize")
async def finalize_case(case_id: uuid.UUID, db: AsyncSession = Depends(_tenant_db)):
    row = (
        await db.execute(
            text("SELECT id, tenant_id, status FROM cases WHERE id = :case_id"),
            {"case_id": case_id},
        )
    ).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Case not found")

    if row["status"] != "draft":
        raise HTTPException(status_code=400, detail="Only draft cases can be finalized")

    # Deterministic placeholder ranking for v0.3.x until engine ranking is wired.
    await db.execute(
        text(
            """
            INSERT INTO case_results (id, case_id, rank, remedy_name, raw_score, created_at)
            VALUES (:id, :case_id, :rank, :remedy_name, :raw_score, now())
            """
        ),
        {
            "id": uuid.uuid4(),
            "case_id": case_id,
            "rank": 1,
            "remedy_name": "TestRemedy",
            "raw_score": 1.0,
        },
    )

    ranking_rows = (
        await db.execute(
            text(
                """
                SELECT rank, remedy_name, raw_score
                FROM case_results
                WHERE case_id = :case_id
                ORDER BY rank ASC, remedy_name ASC
                """
            ),
            {"case_id": case_id},
        )
    ).mappings().all()

    ranking_snapshot = [
        {"rank": int(r["rank"]), "remedy": r["remedy_name"], "score": float(r["raw_score"])}
        for r in ranking_rows
    ]

    canonical_payload = json.dumps(
        ranking_snapshot,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    result_signature = hashlib.sha256(canonical_payload).hexdigest()

    updated = await db.execute(
        text(
            """
            UPDATE cases
            SET status = 'finalized',
                finalized_at = now(),
                ranking_snapshot = CAST(:ranking_snapshot AS jsonb),
                result_signature = :result_signature
            WHERE id = :case_id
              AND status = 'draft'
            """
        ),
        {
            "ranking_snapshot": json.dumps(ranking_snapshot),
            "result_signature": result_signature,
            "case_id": case_id,
        },
    )

    if updated.rowcount != 1:
        raise HTTPException(status_code=400, detail="Only draft cases can be finalized")

    await db.execute(
        text(
            """
            INSERT INTO audit_logs (tenant_id, user_id, action, table_name, record_id, metadata, created_at)
            VALUES (:tenant_id, :user_id, :action, :table_name, :record_id, CAST(:metadata AS jsonb), now())
            """
        ),
        {
            "tenant_id": row["tenant_id"],
            "user_id": uuid.UUID("00000000-0000-0000-0000-000000000000"),
            "action": "FINALIZE",
            "table_name": "cases",
            "record_id": case_id,
            "metadata": json.dumps({"auto": "true", "ts": int(time.time())}),
        },
    )

    return {"case_id": case_id, "status": "finalized", "signature": result_signature}


@router.get("/{case_id}")
async def get_case(case_id: uuid.UUID, db: AsyncSession = Depends(_tenant_db)):
    row = (
        await db.execute(text("SELECT * FROM cases WHERE id = :case_id"), {"case_id": case_id})
    ).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Case not found")

    return dict(row)
