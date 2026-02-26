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
async def tenant_and_patient():
    tenant_id = uuid.uuid4()
    patient_id = uuid.uuid4()

    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO tenants (id, name, created_at) VALUES (:id, :name, now())"),
            {"id": str(tenant_id), "name": f"audit_tenant_{tenant_id.hex[:8]}"},
        )

    async with tenant_session(str(tenant_id)) as session:
        await session.execute(
            text(
                """
                INSERT INTO patients (id, tenant_id, full_name, created_at)
                VALUES (:id, :tenant_id, :full_name, now())
                """
            ),
            {
                "id": str(patient_id),
                "tenant_id": str(tenant_id),
                "full_name": "Audit Test Patient",
            },
        )
        await session.flush()

    return str(tenant_id), str(patient_id)


@pytest.mark.asyncio
async def test_access_audit_view_and_verify(tenant_and_patient):
    tenant_id, patient_id = tenant_and_patient

    app = FastAPI()
    app.include_router(case_router)

    headers = {"X-Tenant-ID": tenant_id}
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        create_resp = await client.post(
            "/cases",
            headers=headers,
            json={"patient_id": patient_id, "input_payload": {"symptom_ids": [1, 2, 3]}},
        )
        assert create_resp.status_code == 200, create_resp.text
        case_id = create_resp.json()["case_id"]

        finalize_resp = await client.post(f"/cases/{case_id}/finalize", headers=headers)
        assert finalize_resp.status_code == 200, finalize_resp.text

        get_resp = await client.get(f"/cases/{case_id}", headers=headers)
        assert get_resp.status_code == 200, get_resp.text

        verify_resp = await client.post(f"/cases/{case_id}/verify-replay", headers=headers)
        assert verify_resp.status_code == 200, verify_resp.text
        assert verify_resp.json()["ok"] is True

    async with tenant_session(tenant_id) as session:
        count_row = (
            await session.execute(
                text(
                    "SELECT COUNT(*) AS cnt FROM access_logs WHERE case_id = :case_id"
                ),
                {"case_id": case_id},
            )
        ).mappings().first()
        cnt = count_row["cnt"]

    assert cnt == 2, f"Expected 2 access_log entries (VIEW + VERIFY), got {cnt}"

    async with tenant_session(tenant_id) as session:
        actions_rows = (
            await session.execute(
                text(
                    "SELECT action FROM access_logs WHERE case_id = :case_id ORDER BY accessed_at"
                ),
                {"case_id": case_id},
            )
        ).mappings().all()
        actions = [r["action"] for r in actions_rows]

    assert "VIEW" in actions, f"Missing VIEW in {actions}"
    assert "VERIFY" in actions, f"Missing VERIFY in {actions}"


@pytest.mark.asyncio
async def test_access_audit_tenant_isolation(tenant_and_patient):
    """Tenant A cannot see Tenant B access_logs."""
    tenant_a_id, patient_a_id = tenant_and_patient

    tenant_b_id = str(uuid.uuid4())
    patient_b_id = str(uuid.uuid4())

    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO tenants (id, name, created_at) VALUES (:id, :name, now())"),
            {"id": tenant_b_id, "name": f"audit_tenant_b_{tenant_b_id[:8]}"},
        )

    async with tenant_session(tenant_b_id) as session:
        await session.execute(
            text(
                """
                INSERT INTO patients (id, tenant_id, full_name, created_at)
                VALUES (:id, :tenant_id, :full_name, now())
                """
            ),
            {
                "id": patient_b_id,
                "tenant_id": tenant_b_id,
                "full_name": "Audit Tenant B Patient",
            },
        )
        await session.flush()

    app = FastAPI()
    app.include_router(case_router)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        create_b = await client.post(
            "/cases",
            headers={"X-Tenant-ID": tenant_b_id},
            json={"patient_id": patient_b_id, "input_payload": {"symptom_ids": [9, 8]}},
        )
        assert create_b.status_code == 200, create_b.text
        case_b_id = create_b.json()["case_id"]

        await client.post(f"/cases/{case_b_id}/finalize", headers={"X-Tenant-ID": tenant_b_id})
        await client.get(f"/cases/{case_b_id}", headers={"X-Tenant-ID": tenant_b_id})

    async with tenant_session(tenant_a_id) as session:
        count_row = (
            await session.execute(
                text(
                    "SELECT COUNT(*) AS cnt FROM access_logs WHERE case_id = :case_id"
                ),
                {"case_id": case_b_id},
            )
        ).mappings().first()
        cnt_from_a = count_row["cnt"]

    assert cnt_from_a == 0, (
        f"Tenant A should see 0 logs for Tenant B case, got {cnt_from_a}"
    )
