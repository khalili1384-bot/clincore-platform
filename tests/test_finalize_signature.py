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
            {"id": str(tenant_id), "name": f"sig_tenant_{tenant_id.hex[:8]}"},
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
                "full_name": "Signature Test Patient",
            },
        )
        await session.flush()

    return str(tenant_id), str(patient_id)


@pytest.mark.asyncio
async def test_finalize_sets_signature_and_finalized_is_immutable(tenant_and_patient):
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
        case_data = get_resp.json()

        result_signature = case_data.get("result_signature")
        assert result_signature
        assert len(result_signature) == 64
        assert case_data.get("status") == "finalized"

    async with tenant_session(tenant_id) as session:
        with pytest.raises(Exception):
            await session.execute(
                text("UPDATE cases SET random_seed = 'tampered' WHERE id = :case_id"),
                {"case_id": case_id},
            )
            await session.flush()
