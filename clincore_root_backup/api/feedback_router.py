"""
Feedback endpoints for v0.4.6.
POST /mcare/feedback       — insert feedback record (RLS-safe, append-only)
GET  /mcare/feedback/summary — tenant-scoped analytics
GET  /admin/mcare/feedback   — admin tenant-scoped feedback stats
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from clincore.api.auth_api_keys import get_api_key_tenant
from clincore.api.admin import get_admin_tenant
from clincore.api.feedback import (
    FeedbackIn,
    FeedbackOut,
    FeedbackSummaryOut,
    canonical_json_dumps,
    narrative_hash,
)
from clincore.db import tenant_session

router = APIRouter(tags=["mcare-feedback"])


async def _get_tenant_from_header(
    request: Request,
    x_api_key: str | None = None,
) -> str:
    """
    Resolve tenant_id from X-API-Key or X-Tenant-ID header.
    Tries API key first; falls back to X-Tenant-ID for direct calls.
    """
    from fastapi import Header

    x_api_key = request.headers.get("X-API-Key")
    x_tenant_id = request.headers.get("X-Tenant-ID") or request.headers.get("X-Tenant-Id")

    if x_api_key:
        return await get_api_key_tenant(request, x_api_key)

    if x_tenant_id:
        return x_tenant_id

    raise HTTPException(
        status_code=401,
        detail="Missing auth: provide X-API-Key or X-Tenant-ID header",
    )


@router.post("/mcare/feedback", response_model=FeedbackOut)
async def post_feedback(
    payload: FeedbackIn,
    request: Request,
) -> FeedbackOut:
    """
    Record physician/user feedback about a predicted remedy.
    Insert-only (RLS prevents UPDATE/DELETE).
    """
    tenant_id = await _get_tenant_from_header(request)

    # Compute narrative hash if narrative provided (never store raw narrative)
    n_hash: str | None = None
    if payload.narrative:
        n_hash = narrative_hash(payload.narrative, payload.locale)

    # Ensure predicted_top1 is in predicted_top3 (best-effort, not enforced as error)
    top3 = payload.predicted_top3
    if payload.predicted_top1 not in top3:
        top3 = [payload.predicted_top1, *top3[:4]]

    # Serialize JSONB fields deterministically
    predicted_top3_json = canonical_json_dumps(top3)
    metadata_json = canonical_json_dumps(payload.metadata or {})

    feedback_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    async with tenant_session(tenant_id) as session:
        await session.execute(
            text(
                """
                INSERT INTO mcare_feedback (
                    id, tenant_id, user_id, case_id, request_id, locale,
                    narrative_hash, predicted_top1, predicted_top3, chosen_remedy,
                    outcome_type, outcome_score, notes, metadata, created_at
                ) VALUES (
                    :id, :tenant_id, :user_id, :case_id, :request_id, :locale,
                    :narrative_hash, :predicted_top1, CAST(:predicted_top3 AS jsonb),
                    :chosen_remedy, :outcome_type, :outcome_score, :notes,
                    CAST(:metadata AS jsonb), :created_at
                )
                """
            ),
            {
                "id": feedback_id,
                "tenant_id": tenant_id,
                "user_id": None,
                "case_id": payload.case_id,
                "request_id": payload.request_id,
                "locale": payload.locale,
                "narrative_hash": n_hash,
                "predicted_top1": payload.predicted_top1,
                "predicted_top3": predicted_top3_json,
                "chosen_remedy": payload.chosen_remedy,
                "outcome_type": payload.outcome_type,
                "outcome_score": payload.outcome_score,
                "notes": payload.notes,
                "metadata": metadata_json,
                "created_at": now,
            },
        )

    return FeedbackOut(
        id=feedback_id,
        created_at=now,
        is_correct=(payload.chosen_remedy == payload.predicted_top1),
    )


@router.get("/mcare/feedback/summary", response_model=FeedbackSummaryOut)
async def get_feedback_summary(
    request: Request,
    days: int = 30,
) -> FeedbackSummaryOut:
    """
    Tenant-scoped feedback analytics.
    Returns accuracy summary and confusion signals for the past `days` days.
    """
    if days < 1 or days > 365:
        raise HTTPException(status_code=400, detail="days must be between 1 and 365")

    tenant_id = await _get_tenant_from_header(request)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    async with tenant_session(tenant_id) as session:
        # Total count
        total_row = (
            await session.execute(
                text(
                    "SELECT COUNT(*) FROM mcare_feedback WHERE created_at >= :cutoff"
                ),
                {"cutoff": cutoff},
            )
        ).fetchone()
        total_count = int(total_row[0]) if total_row else 0

        if total_count == 0:
            return FeedbackSummaryOut(
                total_count=0,
                top1_accuracy=0.0,
                top3_coverage=0.0,
                outcome_counts={},
                top_mismatches=[],
                days=days,
            )

        # Top-1 accuracy: chosen_remedy == predicted_top1
        top1_row = (
            await session.execute(
                text(
                    """
                    SELECT COUNT(*) FROM mcare_feedback
                    WHERE created_at >= :cutoff
                      AND chosen_remedy = predicted_top1
                    """
                ),
                {"cutoff": cutoff},
            )
        ).fetchone()
        top1_correct = int(top1_row[0]) if top1_row else 0

        # Top-3 coverage: chosen_remedy appears in predicted_top3 array
        top3_row = (
            await session.execute(
                text(
                    """
                    SELECT COUNT(*) FROM mcare_feedback
                    WHERE created_at >= :cutoff
                      AND predicted_top3 @> to_jsonb(chosen_remedy)
                    """
                ),
                {"cutoff": cutoff},
            )
        ).fetchone()
        top3_covered = int(top3_row[0]) if top3_row else 0

        # Outcome counts
        outcome_rows = (
            await session.execute(
                text(
                    """
                    SELECT outcome_type, COUNT(*) AS cnt
                    FROM mcare_feedback
                    WHERE created_at >= :cutoff
                    GROUP BY outcome_type
                    ORDER BY cnt DESC
                    """
                ),
                {"cutoff": cutoff},
            )
        ).fetchall()

        # Top mismatches: predicted_top1 != chosen_remedy
        mismatch_rows = (
            await session.execute(
                text(
                    """
                    SELECT predicted_top1, chosen_remedy, COUNT(*) AS cnt
                    FROM mcare_feedback
                    WHERE created_at >= :cutoff
                      AND chosen_remedy != predicted_top1
                    GROUP BY predicted_top1, chosen_remedy
                    ORDER BY cnt DESC
                    LIMIT 10
                    """
                ),
                {"cutoff": cutoff},
            )
        ).fetchall()

    return FeedbackSummaryOut(
        total_count=total_count,
        top1_accuracy=round(top1_correct / total_count, 4) if total_count else 0.0,
        top3_coverage=round(top3_covered / total_count, 4) if total_count else 0.0,
        outcome_counts={r[0]: int(r[1]) for r in outcome_rows},
        top_mismatches=[
            {"predicted_top1": r[0], "chosen_remedy": r[1], "count": int(r[2])}
            for r in mismatch_rows
        ],
        days=days,
    )


@router.get("/admin/mcare/feedback")
async def admin_get_feedback_stats(
    tenant_id: str = Depends(get_admin_tenant),
    days: int = 30,
) -> dict[str, Any]:
    """
    Admin-scoped feedback stats for the calling tenant.
    Requires API key with role='admin'.
    Returns aggregated counts + accuracy metrics.
    """
    if days < 1 or days > 365:
        raise HTTPException(status_code=400, detail="days must be between 1 and 365")

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    async with tenant_session(tenant_id) as session:
        total_row = (
            await session.execute(
                text(
                    "SELECT COUNT(*) FROM mcare_feedback WHERE created_at >= :cutoff"
                ),
                {"cutoff": cutoff},
            )
        ).fetchone()
        total_count = int(total_row[0]) if total_row else 0

        top1_row = (
            await session.execute(
                text(
                    """
                    SELECT COUNT(*) FROM mcare_feedback
                    WHERE created_at >= :cutoff
                      AND chosen_remedy = predicted_top1
                    """
                ),
                {"cutoff": cutoff},
            )
        ).fetchone()
        top1_correct = int(top1_row[0]) if top1_row else 0

        outcome_rows = (
            await session.execute(
                text(
                    """
                    SELECT outcome_type, COUNT(*) AS cnt
                    FROM mcare_feedback
                    WHERE created_at >= :cutoff
                    GROUP BY outcome_type
                    ORDER BY cnt DESC
                    """
                ),
                {"cutoff": cutoff},
            )
        ).fetchall()

    return {
        "tenant_id": tenant_id,
        "days": days,
        "total_feedback_count": total_count,
        "top1_accuracy": round(top1_correct / total_count, 4) if total_count else 0.0,
        "outcome_counts": {r[0]: int(r[1]) for r in outcome_rows},
    }
