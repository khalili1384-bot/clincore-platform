import asyncio
import sys

# 👇 مهم برای Windows
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy import text
from clincore.db import AsyncSessionFactory


async def main():
    async with AsyncSessionFactory() as session:
        result = await session.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;")
        )
        tables = [row[0] for row in result.fetchall()]
        print("TABLES:", tables)


if __name__ == "__main__":
    asyncio.run(main())