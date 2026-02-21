import asyncio
from sqlalchemy import text

from clincore.db import session_scope


async def main():
    async with session_scope() as s:
        res = await s.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;"))
        print("TABLES:", [r[0] for r in res.all()])


if __name__ == "__main__":
    asyncio.run(main())
