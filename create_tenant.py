import asyncio
from uuid import uuid4
from sqlalchemy import text
from src.clincore.core.db import admin_engine

async def main():
    tenant_id = str(uuid4())
    async with admin_engine.begin() as conn:
        await conn.execute(
            text("""
                INSERT INTO tenants (id, name, created_at)
                VALUES (:id, :name, now())
                ON CONFLICT (name) DO NOTHING
            """),
            {"id": tenant_id, "name": "Dr Sofia Clinic"}
        )
        print(f'✅ doctor-tenant created: {tenant_id}')
        print(f'   Name: Dr Sofia Clinic')

if __name__ == "__main__":
    asyncio.run(main())
