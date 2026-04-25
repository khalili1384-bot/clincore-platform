"""Phase 16: Super Admin API tests"""
import os
import pytest
from clincore.core.config import settings

DOCTOR_TENANT_ID = "5c091694-0e5a-46a0-b1d5-01fb7655f0ab"
SUPER_ADMIN_KEY = os.getenv("SUPER_ADMIN_KEY", settings.SUPER_ADMIN_KEY)


@pytest.mark.asyncio
async def test_super_admin_no_key(async_client):
    """GET /super-admin/tenants without header → expect 401"""
    response = await async_client.get("/super-admin/tenants")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_super_admin_wrong_key(async_client):
    """GET /super-admin/tenants with wrong key → expect 401"""
    response = await async_client.get(
        "/super-admin/tenants",
        headers={"X-Super-Admin-Key": "wrong-key-12345"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_super_admin_list_tenants(async_client):
    """GET /super-admin/tenants with correct X-Super-Admin-Key → expect 200 + list"""
    response = await async_client.get(
        "/super-admin/tenants",
        headers={"X-Super-Admin-Key": SUPER_ADMIN_KEY}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] == True
    assert "tenants" in data
    assert isinstance(data["tenants"], list)
    # At least the doctor tenant should be in the list
    assert len(data["tenants"]) >= 1


@pytest.mark.asyncio
async def test_super_admin_list_api_keys(async_client):
    """GET /super-admin/api-keys with correct key → expect 200 + list"""
    response = await async_client.get(
        "/super-admin/api-keys",
        headers={"X-Super-Admin-Key": SUPER_ADMIN_KEY}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] == True
    assert "api_keys" in data
    assert isinstance(data["api_keys"], list)
    # Check structure of first key if any exist
    if len(data["api_keys"]) > 0:
        key = data["api_keys"][0]
        assert "id" in key
        assert "tenant_id" in key
        assert "role" in key
        assert "is_active" in key
        assert "created_at" in key


@pytest.mark.asyncio
async def test_super_admin_tenant_usage(async_client):
    """GET /super-admin/tenants/{DOCTOR_TENANT_ID}/usage → expect 200"""
    response = await async_client.get(
        f"/super-admin/tenants/{DOCTOR_TENANT_ID}/usage",
        headers={"X-Super-Admin-Key": SUPER_ADMIN_KEY}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] == True
    assert "tenant_id" in data
    assert data["tenant_id"] == DOCTOR_TENANT_ID
    assert "usage_today" in data
    assert isinstance(data["usage_today"], list)


@pytest.mark.asyncio
async def test_super_admin_deactivate_reactivate(async_client):
    """Deactivate API key, check False, reactivate, check True"""
    # First, list API keys to find one
    response = await async_client.get(
        "/super-admin/api-keys",
        headers={"X-Super-Admin-Key": SUPER_ADMIN_KEY}
    )
    assert response.status_code == 200
    data = response.json()
    
    if len(data["api_keys"]) == 0:
        pytest.skip("No API keys available for testing")
    
    # Get the first API key
    api_key_id = data["api_keys"][0]["id"]
    
    # Deactivate
    response = await async_client.post(
        f"/super-admin/api-keys/{api_key_id}/deactivate",
        headers={"X-Super-Admin-Key": SUPER_ADMIN_KEY}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] == True
    assert data["is_active"] == False
    
    # Verify deactivated
    response = await async_client.get(
        "/super-admin/api-keys",
        headers={"X-Super-Admin-Key": SUPER_ADMIN_KEY}
    )
    assert response.status_code == 200
    data = response.json()
    key = next((k for k in data["api_keys"] if k["id"] == api_key_id), None)
    assert key is not None
    assert key["is_active"] == False
    
    # Reactivate
    response = await async_client.post(
        f"/super-admin/api-keys/{api_key_id}/activate",
        headers={"X-Super-Admin-Key": SUPER_ADMIN_KEY}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] == True
    assert data["is_active"] == True
    
    # Verify reactivated
    response = await async_client.get(
        "/super-admin/api-keys",
        headers={"X-Super-Admin-Key": SUPER_ADMIN_KEY}
    )
    assert response.status_code == 200
    data = response.json()
    key = next((k for k in data["api_keys"] if k["id"] == api_key_id), None)
    assert key is not None
    assert key["is_active"] == True
