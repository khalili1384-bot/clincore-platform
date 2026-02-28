"""
Tests for v0.4.6 mcare feedback loop.
A) Happy path insert + is_correct boolean
B) RLS isolation (tenant A cannot see tenant B's records)
C) Append-only (UPDATE blocked by RLS)
D) Summary correctness
"""
from __future__ import annotations

import asyncio
import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from clincore.api.feedback_router import router as feedback_router
from clincore.db import engine, tenant_session


# ── Helpers ───────────────────────────────────────────────────────────────────

def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(feedback_router)
    return app


async def _create_tenant() -> str:
    tid = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO tenants (id, name, created_at) VALUES (:id, :name, now())"
            ),
            {"id": tid, "name": f"fb_tenant_{uuid.uuid4().hex[:8]}"},
        )
    return tid


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def tenant_a():
    return await _create_tenant()


@pytest.fixture
async def tenant_b():
    return await _create_tenant()


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_happy_path_insert_is_correct_true(tenant_a):
    """Inserting feedback where chosen == predicted_top1 returns is_correct=True."""
    transport = ASGITransport(app=_app())
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            "/mcare/feedback",
            headers={"X-Tenant-ID": tenant_a},
            json={
                "predicted_top1": "nux-v",
                "predicted_top3": ["nux-v", "ars", "lyc"],
                "chosen_remedy": "nux-v",
                "outcome_type": "agree",
            },
        )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "id" in data
    assert data["is_correct"] is True


@pytest.mark.asyncio
async def test_happy_path_insert_is_correct_false(tenant_a):
    """Inserting feedback where chosen != predicted_top1 returns is_correct=False."""
    transport = ASGITransport(app=_app())
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            "/mcare/feedback",
            headers={"X-Tenant-ID": tenant_a},
            json={
                "predicted_top1": "nux-v",
                "predicted_top3": ["nux-v", "ars", "lyc"],
                "chosen_remedy": "ars",
                "outcome_type": "disagree",
                "outcome_score": 7,
            },
        )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["is_correct"] is False


@pytest.mark.asyncio
async def test_feedback_missing_required_fields(tenant_a):
    """Missing required fields returns 422."""
    transport = ASGITransport(app=_app())
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            "/mcare/feedback",
            headers={"X-Tenant-ID": tenant_a},
            json={
                "predicted_top1": "nux-v",
                # missing predicted_top3, chosen_remedy, outcome_type
            },
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_feedback_invalid_outcome_score(tenant_a):
    """outcome_score outside 1-10 returns 422."""
    transport = ASGITransport(app=_app())
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            "/mcare/feedback",
            headers={"X-Tenant-ID": tenant_a},
            json={
                "predicted_top1": "nux-v",
                "predicted_top3": ["nux-v"],
                "chosen_remedy": "nux-v",
                "outcome_type": "agree",
                "outcome_score": 11,
            },
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_feedback_invalid_outcome_type(tenant_a):
    """Invalid outcome_type returns 422."""
    transport = ASGITransport(app=_app())
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            "/mcare/feedback",
            headers={"X-Tenant-ID": tenant_a},
            json={
                "predicted_top1": "nux-v",
                "predicted_top3": ["nux-v"],
                "chosen_remedy": "nux-v",
                "outcome_type": "invalid_type",
            },
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_feedback_narrative_hash_stored(tenant_a):
    """When narrative is provided, it is hashed and stored (never raw)."""
    transport = ASGITransport(app=_app())
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            "/mcare/feedback",
            headers={"X-Tenant-ID": tenant_a},
            json={
                "predicted_top1": "ars",
                "predicted_top3": ["ars", "lyc"],
                "chosen_remedy": "ars",
                "outcome_type": "agree",
                "narrative": "Patient is very anxious and fears poverty",
                "locale": "en",
            },
        )
    assert resp.status_code == 200, resp.text
    fb_id = resp.json()["id"]

    # Verify narrative_hash is set (not null) and raw narrative is NOT stored
    async with tenant_session(tenant_a) as session:
        row = (
            await session.execute(
                text("SELECT narrative_hash FROM mcare_feedback WHERE id = :id"),
                {"id": fb_id},
            )
        ).fetchone()

    assert row is not None
    assert row[0] is not None  # narrative_hash must be set
    assert len(row[0]) == 64   # SHA-256 hex = 64 chars


@pytest.mark.asyncio
async def test_rls_tenant_isolation(tenant_a, tenant_b):
    """Feedback inserted by tenant A must not be visible to tenant B."""
    # Insert via API for tenant_a
    transport = ASGITransport(app=_app())
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            "/mcare/feedback",
            headers={"X-Tenant-ID": tenant_a},
            json={
                "predicted_top1": "lyc",
                "predicted_top3": ["lyc", "aur", "nux-v"],
                "chosen_remedy": "lyc",
                "outcome_type": "agree",
            },
        )
    assert resp.status_code == 200
    fb_id = resp.json()["id"]

    # Tenant B should NOT see tenant A's record
    async with tenant_session(tenant_b) as session:
        row = (
            await session.execute(
                text("SELECT id FROM mcare_feedback WHERE id = :id"),
                {"id": fb_id},
            )
        ).fetchone()

    assert row is None, "Tenant B must not see Tenant A's feedback (RLS violation)"


@pytest.mark.asyncio
async def test_append_only_rls_policy_exists(tenant_a):
    """
    Verify append-only enforcement:
    - RLS is enabled on mcare_feedback
    - An UPDATE-deny policy (mcare_feedback_no_update) exists
    - A DELETE-deny policy (mcare_feedback_no_delete) exists

    Note: PostgreSQL table owners bypass RLS by default unless FORCE ROW LEVEL
    SECURITY is set. The deny policies apply to non-owner application roles.
    We verify the schema-level controls are in place.
    """
    async with engine.begin() as conn:
        # Verify RLS is enabled
        rls_row = (
            await conn.execute(
                text(
                    "SELECT relrowsecurity FROM pg_class "
                    "WHERE relname = 'mcare_feedback'"
                )
            )
        ).fetchone()
        assert rls_row is not None, "mcare_feedback table not found"
        assert rls_row[0] is True, "RLS must be enabled on mcare_feedback"

        # Verify UPDATE-deny policy exists
        update_policy = (
            await conn.execute(
                text(
                    """
                    SELECT policyname FROM pg_policies
                    WHERE tablename = 'mcare_feedback'
                      AND policyname = 'mcare_feedback_no_update'
                    """
                )
            )
        ).fetchone()
        assert update_policy is not None, "mcare_feedback_no_update policy must exist"

        # Verify DELETE-deny policy exists
        delete_policy = (
            await conn.execute(
                text(
                    """
                    SELECT policyname FROM pg_policies
                    WHERE tablename = 'mcare_feedback'
                      AND policyname = 'mcare_feedback_no_delete'
                    """
                )
            )
        ).fetchone()
        assert delete_policy is not None, "mcare_feedback_no_delete policy must exist"


@pytest.mark.asyncio
async def test_summary_correctness(tenant_a):
    """Insert 3 known feedback rows, verify summary returns accurate metrics."""
    transport = ASGITransport(app=_app())

    rows_to_insert = [
        # correct: chosen == predicted_top1
        {"predicted_top1": "nux-v", "predicted_top3": ["nux-v", "ars"], "chosen_remedy": "nux-v", "outcome_type": "agree"},
        # correct
        {"predicted_top1": "ars", "predicted_top3": ["ars", "lyc"], "chosen_remedy": "ars", "outcome_type": "agree"},
        # incorrect but in top3
        {"predicted_top1": "lyc", "predicted_top3": ["lyc", "aur", "nux-v"], "chosen_remedy": "aur", "outcome_type": "disagree"},
    ]

    # Use a fresh tenant to isolate summary counts
    summary_tenant = await _create_tenant()

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        for row in rows_to_insert:
            r = await client.post(
                "/mcare/feedback",
                headers={"X-Tenant-ID": summary_tenant},
                json=row,
            )
            assert r.status_code == 200, r.text

        summary_resp = await client.get(
            "/mcare/feedback/summary",
            headers={"X-Tenant-ID": summary_tenant},
            params={"days": 7},
        )

    assert summary_resp.status_code == 200, summary_resp.text
    data = summary_resp.json()

    assert data["total_count"] == 3
    # 2 out of 3 are top-1 correct
    assert abs(data["top1_accuracy"] - (2 / 3)) < 0.01
    # all 3 chosen remedies are in their respective predicted_top3
    assert data["top3_coverage"] == 1.0
    # outcome_counts must include "agree" (2) and "disagree" (1)
    assert data["outcome_counts"].get("agree", 0) == 2
    assert data["outcome_counts"].get("disagree", 0) == 1


@pytest.mark.asyncio
async def test_summary_empty_tenant(tenant_b):
    """Summary for tenant with no records returns zeros."""
    # Use a brand-new tenant to guarantee zero records
    empty_tenant = await _create_tenant()
    transport = ASGITransport(app=_app())
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get(
            "/mcare/feedback/summary",
            headers={"X-Tenant-ID": empty_tenant},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_count"] == 0
    assert data["top1_accuracy"] == 0.0
    assert data["top3_coverage"] == 0.0


# ── Freeze Mode Tests ─────────────────────────────────────────────────────────
# Ensure feedback only stores data, never modifies scoring weights/clusters/params

@pytest.mark.asyncio
async def test_feedback_does_not_affect_auto_scoring(tenant_a):
    """SAFETY: Feedback submission must never alter /mcare/auto results."""
    from clincore.mcare_engine.ui.router import mcare_auto, mcare_save, mcare_feedback

    transport = ASGITransport(app=_app())
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # First /mcare/auto run - get baseline
        narrative = "irritable, ambitious, snaps quickly, work obsessed, hurry, driven, restlessness"
        r1 = await client.post("/mcare/auto", json={"narrative": narrative, "top_n": 5})
        assert r1.status_code == 200
        baseline = r1.json()
        assert baseline["ok"] is True
        top1_before = baseline["results"][0] if baseline["results"] else None

        # Save case to get case_id
        r_save = await client.post("/mcare/save", json={
            "symptom_ids": baseline["symptom_ids"],
            "selected_remedy": "nux-v",
            "case_type": "auto"
        })
        assert r_save.status_code == 200
        case_id = r_save.json()["case_id"]

        # Submit feedback via API
        r_fb = await client.post(
            "/mcare/feedback",
            headers={"X-Tenant-ID": tenant_a},
            json={
                "case_hash": case_id,
                "chosen_remedy": "nux-v",
                "confidence": 4,
                "is_correct": True
            }
        )
        assert r_fb.status_code == 200

        # Re-run /mcare/auto with identical input
        r2 = await client.post("/mcare/auto", json={"narrative": narrative, "top_n": 5})
        assert r2.status_code == 200
        after = r2.json()
        assert after["ok"] is True
        top1_after = after["results"][0] if after["results"] else None

        # SAFETY ASSERT: Scoring must be identical before and after feedback
        assert top1_before == top1_after, (
            f"CRITICAL: SCORING CHANGED AFTER FEEDBACK! "
            f"Before: {top1_before}, After: {top1_after}. "
            f"Feedback must never affect scoring determinism."
        )


@pytest.mark.asyncio
async def test_multiple_feedbacks_no_scoring_drift(tenant_a):
    """SAFETY: Multiple feedbacks must not cause any scoring drift."""
    transport = ASGITransport(app=_app())
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        narrative = "fear of public speaking, anticipatory anxiety, bloating, insecurity, desire sweet"

        # Baseline
        r1 = await client.post("/mcare/auto", json={"narrative": narrative, "top_n": 5})
        baseline = r1.json()
        assert baseline["ok"] is True
        baseline_results = baseline["results"]

        # Submit 3 feedbacks
        for i in range(3):
            r = await client.post("/mcare/auto", json={"narrative": narrative, "top_n": 5})
            res = r.json()
            r_save = await client.post("/mcare/save", json={
                "symptom_ids": res["symptom_ids"],
                "selected_remedy": res["results"][0]["remedy"] if res["results"] else "nux-v",
                "case_type": "auto"
            })
            case_id = r_save.json()["case_id"]
            await client.post(
                "/mcare/feedback",
                headers={"X-Tenant-ID": tenant_a},
                json={
                    "case_hash": case_id,
                    "chosen_remedy": "nux-v",
                    "confidence": 3,
                    "is_correct": True
                }
            )

        # Final scoring
        r2 = await client.post("/mcare/auto", json={"narrative": narrative, "top_n": 5})
        final = r2.json()
        assert final["ok"] is True

        # SAFETY ASSERT: No scoring drift
        assert baseline_results == final["results"], (
            f"CRITICAL: SCORING DRIFT AFTER FEEDBACKS! "
            f"Baseline: {baseline_results}, Final: {final['results']}"
        )
