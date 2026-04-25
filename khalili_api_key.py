import asyncio
import secrets
import hashlib
from src.clincore.core.db import tenant_session
from sqlalchemy import text

async def main():
    async with tenant_session('khalili-clinic') as s:
        result = await s.execute(text("SELECT id FROM tenants WHERE name = 'Dr Khalili Clinic' LIMIT 1"))
        tenant = result.fetchone()
        if not tenant:
            print('ERROR: tenant not found')
            return
        tenant_id = str(tenant[0])
        api_key = secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        await s.execute(text(
            "INSERT INTO api_keys (tenant_id, key_hash, label, is_active) VALUES (:tid, :kh, :label, true)"
        ), {"tid": tenant_id, "kh": key_hash, "label": "Dr Khalili Key"})
        await s.commit()
        print(f'✅ Tenant ID: {tenant_id}')
        print(f'✅ API Key: {api_key}')
        print('SAVE THIS KEY - it will not be shown again')

asyncio.run(main())
