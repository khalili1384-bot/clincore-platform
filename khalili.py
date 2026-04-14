import asyncio
from src.clincore.core.db import tenant_session
from sqlalchemy import text

async def main():
    async with tenant_session('khalili-clinic') as s:
        await s.execute(text("INSERT INTO tenants (id, name) VALUES (gen_random_uuid(), 'Dr Khalili Clinic') ON CONFLICT (name) DO NOTHING"))
        await s.commit()
        print('khalili-clinic created')

asyncio.run(main())
