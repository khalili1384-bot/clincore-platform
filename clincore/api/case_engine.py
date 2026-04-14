from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from clincore.db import tenant_session

router = APIRouter(prefix="/cases", tags=["cases"])
_log = logging.getLogger("clincore.access")

_SYSTEM_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def _log_access(
    db: AsyncSession,
    tenant_id: Any,
    case_id: Any,
    action: str,
) -> None:
    """Fire-and-forget single INSERT into access_logs. Never raises."""
    try:
        await db.execute(
            text(
                """
                INSERT INTO access_logs (tenant_id, user_id, case_id, action, accessed_at)
                VALUES (:tenant_id, :user_id, :case_id, :action, now())
                """
            ),
            {
                "tenant_id": tenant_id,
                "user_id": _SYSTEM_USER_ID,
                "case_id": case_id,
                "action": action,
            },
        )
    except Exception as exc:  # noqa: BLE001
        _log.warning("access_log insert failed (non-fatal): %s", exc)


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

    billing_row = (
        await db.execute(
            text(
                """
                SELECT billing_status,
                       (SELECT COUNT(*) FROM usage_events WHERE tenant_id = :tid) AS usage_count
                FROM cases
                WHERE tenant_id = :tid
                LIMIT 1
                """
            ),
            {"tid": tenant_id},
        )
    ).mappings().first()

    if billing_row and billing_row["billing_status"] == "free" and billing_row["usage_count"] > 1000:
        raise HTTPException(
            status_code=402,
            detail="Free tier limit exceeded. Please upgrade to continue.",
        )

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


@router.post("/{case_id}/verify-replay")
async def verify_replay(case_id: uuid.UUID, db: AsyncSession = Depends(_tenant_db)):
    row = (
        await db.execute(
            text(
                "SELECT id, status, result_signature, ranking_snapshot FROM cases WHERE id = :case_id"
            ),
            {"case_id": case_id},
        )
    ).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Case not found")

    if row["status"] != "finalized":
        raise HTTPException(status_code=400, detail="Only finalized cases can be replay-verified")

    expected = row["result_signature"]
    ranking_snapshot = row["ranking_snapshot"]

    if ranking_snapshot is None:
        raise HTTPException(status_code=400, detail="Case has no ranking_snapshot to verify")

    if isinstance(ranking_snapshot, str):
        snapshot_obj = json.loads(ranking_snapshot)
    else:
        snapshot_obj = ranking_snapshot

    canonical_bytes = json.dumps(
        snapshot_obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    computed = hashlib.sha256(canonical_bytes).hexdigest()

    ok = computed == expected

    details = json.dumps({"expected": expected, "computed": computed, "match": ok})

    verified_row = await db.execute(
        text(
            """
            UPDATE cases
            SET replay_verified_at = now(),
                replay_verification_ok = :ok,
                replay_verification_details = CAST(:details AS jsonb)
            WHERE id = :case_id
            RETURNING replay_verified_at
            """
        ),
        {"ok": ok, "details": details, "case_id": case_id},
    )

    verified_at_row = verified_row.mappings().first()
    verified_at = verified_at_row["replay_verified_at"] if verified_at_row else None

    tenant_row = (
        await db.execute(
            text(
                "SELECT NULLIF(current_setting('app.tenant_id', true), '')::uuid AS tenant_id"
            )
        )
    ).mappings().first()
    tenant_id_for_log = tenant_row["tenant_id"] if tenant_row else None
    await _log_access(db, tenant_id_for_log, case_id, "VERIFY")

    return {
        "ok": ok,
        "case_id": str(case_id),
        "expected": expected,
        "computed": computed,
        "verified_at": str(verified_at) if verified_at else None,
    }


@router.get("/{case_id}")
async def get_case(case_id: uuid.UUID, db: AsyncSession = Depends(_tenant_db)):
    row = (
        await db.execute(text("SELECT * FROM cases WHERE id = :case_id"), {"case_id": case_id})
    ).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Case not found")

    await _log_access(db, row["tenant_id"], case_id, "VIEW")

    return dict(row)
