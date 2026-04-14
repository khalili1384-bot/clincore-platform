"""
Bootstrap router — single-use tenant + API key provisioning.
Requires BOOTSTRAP_TOKEN env var to be set. Disabled if not set.
"""
from __future__ import annotations

import os
import secrets
import uuid

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy import text

from clincore.db import engine as _engine
from clincore.api.auth_api_keys import _hash_key

router = APIRouter(prefix="/bootstrap", tags=["bootstrap"])

_BOOTSTRAP_TOKEN = os.getenv("BOOTSTRAP_TOKEN", "")


def _check_token(authorization: str | None) -> None:
    if not _BOOTSTRAP_TOKEN:
        raise HTTPException(status_code=503, detail="Bootstrap is disabled (BOOTSTRAP_TOKEN not set)")
    expected = f"Bearer {_BOOTSTRAP_TOKEN}"
    if not authorization or not secrets.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Invalid bootstrap token")


class BootstrapRequest(BaseModel):
    tenant_name: str
    admin_email: str | None = None


class BootstrapResponse(BaseModel):
    tenant_id: str
    api_key: str
    message: str


@router.post("", response_model=BootstrapResponse, status_code=201)
async def bootstrap_tenant(
    payload: BootstrapRequest,
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    """
    Create a new tenant and return a raw API key.
    Requires Authorization: Bearer <BOOTSTRAP_TOKEN>.
    """
    _check_token(authorization)

    tenant_id = uuid.uuid4()
    raw_key = secrets.token_urlsafe(32)
    key_hash = _hash_key(raw_key)

    async with _engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO tenants (id, name, created_at) VALUES (:id, :name, now()) "
                "ON CONFLICT (name) DO NOTHING"
            ),
            {"id": str(tenant_id), "name": payload.tenant_name},
        )
        existing = (
            await conn.execute(
                text("SELECT id FROM tenants WHERE name = :name"),
                {"name": payload.tenant_name},
            )
        ).fetchone()
        if existing:
            tenant_id = existing[0]

        await conn.execute(
            text(
                """
                INSERT INTO api_keys (id, tenant_id, key_hash, label, is_active, created_at)
                VALUES (:id, :tenant_id, :key_hash, :label, true, now())
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "tenant_id": str(tenant_id),
                "key_hash": key_hash,
                "label": f"bootstrap-{payload.tenant_name}",
            },
        )

    return BootstrapResponse(
        tenant_id=str(tenant_id),
        api_key=raw_key,
        message=f"Tenant '{payload.tenant_name}' provisioned.",
    )
