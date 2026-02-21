from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.shared.db import TENANT_GUC, in_tenant_tx


@pytest.mark.asyncio
async def test_select_without_tenant_context_sees_nothing(app_engine: AsyncEngine, seed_patients) -> None:
    async with app_engine.begin() as conn:
        res = await conn.execute(text("SELECT count(*) FROM patients"))
        # fail-closed: missing tenant context must match nothing (0 rows visible)
        assert res.scalar_one() == 0


@pytest.mark.asyncio
async def test_insert_without_tenant_context_fails(app_engine: AsyncEngine, tenants) -> None:
    t1, _ = tenants
    async with app_engine.begin() as conn:
        with pytest.raises(Exception):
            await conn.execute(
                text("INSERT INTO patients (id, tenant_id, full_name) VALUES (:id, :tenant_id, :full_name)"),
                {"id": uuid4(), "tenant_id": t1, "full_name": "Should Fail"},
            )


@pytest.mark.asyncio
async def test_in_tenant_tx_sets_context_and_allows_own_rows(app_engine: AsyncEngine, tenants, seed_patients) -> None:
    t1, t2 = tenants

    async def _count(conn) -> int:
        res = await conn.execute(text("SELECT count(*) FROM patients"))
        return int(res.scalar_one())

    # tenant 1 sees only tenant 1 row
    c1 = await in_tenant_tx(t1, _count)
    assert c1 == 1

    # tenant 2 sees only tenant 2 row
    c2 = await in_tenant_tx(t2, _count)
    assert c2 == 1


@pytest.mark.asyncio
async def test_cross_tenant_access_impossible(app_engine: AsyncEngine, tenants, seed_patients) -> None:
    t1, t2 = tenants

    async def _names(conn) -> list[str]:
        res = await conn.execute(text("SELECT full_name FROM patients ORDER BY full_name"))
        return [r[0] for r in res.fetchall()]

    names_t1 = await in_tenant_tx(t1, _names)
    names_t2 = await in_tenant_tx(t2, _names)

    assert names_t1 == ["Alice A"]
    assert names_t2 == ["Bob B"]
