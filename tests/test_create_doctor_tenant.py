"""Phase 16: Create doctor tenant and API key"""
import asyncio
import hashlib
import secrets
from uuid import uuid4

import pytest
from sqlalchemy import text

from clincore.core.db import admin_engine


@pytest.mark.asyncio
async def test_create_doctor_tenant():
    """Create doctor-tenant for Phase 16"""
    tenant_id = str(uuid4())
    
    async with admin_engine.begin() as conn:
        # Create tenant (or get existing)
        result = await conn.execute(
            text("""
                INSERT INTO tenants (id, name, created_at)
                VALUES (:id, :name, now())
                ON CONFLICT (name) DO NOTHING
                RETURNING id
            """),
            {"id": tenant_id, "name": "Dr Sofia Clinic"}
        )
        
        # Get tenant ID (from INSERT or SELECT if already exists)
        returned_id = result.scalar()
        if returned_id is None:
            # Tenant already existed, fetch its ID
            result = await conn.execute(
                text("SELECT id FROM tenants WHERE name = :name"),
                {"name": "Dr Sofia Clinic"}
            )
            tenant_id = str(result.scalar())
        else:
            tenant_id = str(returned_id)
        
        print(f"\n✅ Tenant created: {tenant_id}")
        print(f"   Name: Dr Sofia Clinic")
        
        # Create API key
        raw_key = secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        
        await conn.execute(
            text("""
                INSERT INTO api_keys (id, tenant_id, key_hash, label, is_active, created_at)
                VALUES (gen_random_uuid(), :tenant_id, :key_hash, 'Dr Sofia API', true, now())
                ON CONFLICT (key_hash) DO NOTHING
            """),
            {"tenant_id": tenant_id, "key_hash": key_hash}
        )
        
        print(f"\n✅ API Key created:")
        print(f"   Raw Key: {raw_key}")
        print(f"   Tenant ID: {tenant_id}")
        print(f"\n📋 Test command:")
        print(f'curl -X POST "http://localhost:8000/mcare/auto" \\')
        print(f'  -H "X-Tenant-Id: {tenant_id}" \\')
        print(f'  -H "X-API-Key: {raw_key}" \\')
        print(f'  -H "Content-Type: application/json" \\')
        print(f'  -d \'{{"text": "ترس مالی شدید، وسواس نظم، بی‌خوابی نیمه‌شب"}}\'')
