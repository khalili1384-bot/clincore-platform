"""
Tests for v1 Cases API endpoints:
- POST /cases  (create)
- POST /cases/{id}/finalize
- GET  /cases/{id}
- POST /cases/{id}/verify-replay
Billing skeleton: newly created case has billing_status = 'free'
No external network required; uses ASGITransport + httpx.
"""
from __future__ import annotations

import asyncio
import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from clincore.api.case_engine import router as case_router
from clincore.db import engine, tenant_session


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def tenant_patient():
    tenant_id = str(uuid.uuid4())
    patient_id = str(uuid.uuid4())

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO tenants (id, name, created_at) VALUES (:id, :name, now())"
            ),
            {"id": tenant_id, "name": f"v1_tenant_{uuid.uuid4().hex[:8]}"},
        )

    async with tenant_session(tenant_id) as session:
        await session.execute(
            text(
                "INSERT INTO patients (id, tenant_id, full_name, created_at) "
                "VALUES (:id, :tenant_id, :name, now())"
            ),
            {"id": patient_id, "tenant_id": tenant_id, "name": "V1 Test Patient"},
        )
        await session.flush()

    return tenant_id, patient_id


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(case_router)
    return app


@pytest.mark.asyncio
async def test_create_case_returns_draft(tenant_patient):
    tenant_id, patient_id = tenant_patient
    transport = ASGITransport(app=_app())

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            "/cases",
            headers={"X-Tenant-ID": tenant_id},
            json={"patient_id": patient_id, "input_payload": {"symptom_ids": [1, 2]}},
        )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "draft"
    assert "case_id" in data


@pytest.mark.asyncio
async def test_new_case_billing_status_is_free(tenant_patient):
    """Billing skeleton: newly created case must have billing_status = 'free'."""
    tenant_id, patient_id = tenant_patient
    transport = ASGITransport(app=_app())

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            "/cases",
            headers={"X-Tenant-ID": tenant_id},
            json={"patient_id": patient_id, "input_payload": {"symptom_ids": [5]}},
        )
    assert resp.status_code == 200, resp.text
    case_id = resp.json()["case_id"]

    async with tenant_session(tenant_id) as session:
        row = (
            await session.execute(
                text(
                    "SELECT billing_status, api_client_id FROM cases WHERE id = :id"
                ),
                {"id": case_id},
            )
        ).mappings().first()

    assert row is not None
    assert row["billing_status"] == "free", (
        f"Expected billing_status='free', got '{row['billing_status']}'"
    )
    assert row["api_client_id"] is None


@pytest.mark.asyncio
async def test_finalize_case(tenant_patient):
    tenant_id, patient_id = tenant_patient
    transport = ASGITransport(app=_app())

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        create_resp = await client.post(
            "/cases",
            headers={"X-Tenant-ID": tenant_id},
            json={"patient_id": patient_id, "input_payload": {"symptom_ids": [3]}},
        )
        assert create_resp.status_code == 200
        case_id = create_resp.json()["case_id"]

        fin_resp = await client.post(
            f"/cases/{case_id}/finalize",
            headers={"X-Tenant-ID": tenant_id},
        )

    assert fin_resp.status_code == 200, fin_resp.text
    data = fin_resp.json()
    assert data["status"] == "finalized"
    assert len(data["signature"]) == 64  # SHA-256 hex


@pytest.mark.asyncio
async def test_get_case(tenant_patient):
    tenant_id, patient_id = tenant_patient
    transport = ASGITransport(app=_app())

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        create_resp = await client.post(
            "/cases",
            headers={"X-Tenant-ID": tenant_id},
            json={"patient_id": patient_id, "input_payload": {"symptom_ids": [7]}},
        )
        case_id = create_resp.json()["case_id"]

        get_resp = await client.get(
            f"/cases/{case_id}",
            headers={"X-Tenant-ID": tenant_id},
        )

    assert get_resp.status_code == 200, get_resp.text
    data = get_resp.json()
    assert str(data["id"]) == case_id


@pytest.mark.asyncio
async def test_get_case_not_found(tenant_patient):
    tenant_id, _ = tenant_patient
    transport = ASGITransport(app=_app())

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get(
            f"/cases/{uuid.uuid4()}",
            headers={"X-Tenant-ID": tenant_id},
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_verify_replay(tenant_patient):
    tenant_id, patient_id = tenant_patient
    transport = ASGITransport(app=_app())

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        create_resp = await client.post(
            "/cases",
            headers={"X-Tenant-ID": tenant_id},
            json={"patient_id": patient_id, "input_payload": {"symptom_ids": [10, 11]}},
        )
        case_id = create_resp.json()["case_id"]

        await client.post(
            f"/cases/{case_id}/finalize",
            headers={"X-Tenant-ID": tenant_id},
        )

        verify_resp = await client.post(
            f"/cases/{case_id}/verify-replay",
            headers={"X-Tenant-ID": tenant_id},
        )

    assert verify_resp.status_code == 200, verify_resp.text
    assert verify_resp.json()["ok"] is True


@pytest.mark.asyncio
async def test_verify_replay_fails_on_draft(tenant_patient):
    tenant_id, patient_id = tenant_patient
    transport = ASGITransport(app=_app())

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        create_resp = await client.post(
            "/cases",
            headers={"X-Tenant-ID": tenant_id},
            json={"patient_id": patient_id, "input_payload": {"symptom_ids": [99]}},
        )
        case_id = create_resp.json()["case_id"]

        verify_resp = await client.post(
            f"/cases/{case_id}/verify-replay",
            headers={"X-Tenant-ID": tenant_id},
        )

    assert verify_resp.status_code == 400


@pytest.mark.asyncio
async def test_case_tenant_isolation(tenant_patient):
    """Case created by tenant A must not be visible to tenant B."""
    tenant_a_id, patient_a_id = tenant_patient

    tenant_b_id = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO tenants (id, name, created_at) VALUES (:id, :name, now())"
            ),
            {"id": tenant_b_id, "name": f"v1_tenant_b_{uuid.uuid4().hex[:6]}"},
        )

    transport = ASGITransport(app=_app())
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        create_resp = await client.post(
            "/cases",
            headers={"X-Tenant-ID": tenant_a_id},
            json={"patient_id": patient_a_id, "input_payload": {"symptom_ids": [4]}},
        )
        case_id = create_resp.json()["case_id"]

        get_resp = await client.get(
            f"/cases/{case_id}",
            headers={"X-Tenant-ID": tenant_b_id},
        )

    assert get_resp.status_code == 404, (
        "Tenant B should not be able to see Tenant A's case"
    )
