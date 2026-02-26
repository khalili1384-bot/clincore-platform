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
            {"id": str(tenant_id), "name": f"replay_tenant_{tenant_id.hex[:8]}"},
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
                "full_name": "Replay Test Patient",
            },
        )
        await session.flush()

    return str(tenant_id), str(patient_id)


@pytest.mark.asyncio
async def test_verify_replay_passes_for_untouched_finalized_case(tenant_and_patient):
    tenant_id, patient_id = tenant_and_patient

    app = FastAPI()
    app.include_router(case_router)

    headers = {"X-Tenant-ID": tenant_id}
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        create_resp = await client.post(
            "/cases",
            headers=headers,
            json={"patient_id": patient_id, "input_payload": {"symptom_ids": [10, 20, 30]}},
        )
        assert create_resp.status_code == 200, create_resp.text
        case_id = create_resp.json()["case_id"]

        finalize_resp = await client.post(f"/cases/{case_id}/finalize", headers=headers)
        assert finalize_resp.status_code == 200, finalize_resp.text
        fin_data = finalize_resp.json()
        assert fin_data.get("signature"), "finalize must return a signature"
        assert len(fin_data["signature"]) == 64

        verify_resp = await client.post(f"/cases/{case_id}/verify-replay", headers=headers)
        assert verify_resp.status_code == 200, verify_resp.text
        v = verify_resp.json()

        assert v["ok"] is True
        assert v["case_id"] == case_id
        assert v["expected"] == v["computed"]
        assert len(v["expected"]) == 64
        assert v["verified_at"] is not None


@pytest.mark.asyncio
async def test_verify_replay_fails_on_non_finalized_case(tenant_and_patient):
    tenant_id, patient_id = tenant_and_patient

    app = FastAPI()
    app.include_router(case_router)

    headers = {"X-Tenant-ID": tenant_id}
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        create_resp = await client.post(
            "/cases",
            headers=headers,
            json={"patient_id": patient_id, "input_payload": {"symptom_ids": [1, 2]}},
        )
        assert create_resp.status_code == 200, create_resp.text
        case_id = create_resp.json()["case_id"]

        verify_resp = await client.post(f"/cases/{case_id}/verify-replay", headers=headers)
        assert verify_resp.status_code == 400
        assert "finalized" in verify_resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_verify_replay_stable_after_immutability_block(tenant_and_patient):
    """
    After a finalized case is tamper-blocked by the DB trigger,
    re-verify must still return ok=True.
    We do NOT bypass RLS or use superuser.
    """
    tenant_id, patient_id = tenant_and_patient

    app = FastAPI()
    app.include_router(case_router)

    headers = {"X-Tenant-ID": tenant_id}
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        create_resp = await client.post(
            "/cases",
            headers=headers,
            json={"patient_id": patient_id, "input_payload": {"symptom_ids": [5, 6, 7]}},
        )
        assert create_resp.status_code == 200, create_resp.text
        case_id = create_resp.json()["case_id"]

        finalize_resp = await client.post(f"/cases/{case_id}/finalize", headers=headers)
        assert finalize_resp.status_code == 200, finalize_resp.text

        verify_resp1 = await client.post(f"/cases/{case_id}/verify-replay", headers=headers)
        assert verify_resp1.status_code == 200, verify_resp1.text
        v1 = verify_resp1.json()
        assert v1["ok"] is True

    async with tenant_session(tenant_id) as session:
        try:
            await session.execute(
                text("UPDATE cases SET random_seed = 'tampered' WHERE id = :case_id"),
                {"case_id": case_id},
            )
            await session.flush()
        except Exception:
            pass

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        verify_resp2 = await client.post(f"/cases/{case_id}/verify-replay", headers=headers)
        assert verify_resp2.status_code == 200, verify_resp2.text
        v2 = verify_resp2.json()
        assert v2["ok"] is True
        assert v2["expected"] == v2["computed"]
