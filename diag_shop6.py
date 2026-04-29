import asyncio, os, sys
sys.path.insert(0, r'D:\clincore-platform\src')
os.environ.setdefault('DATABASE_URL', 'postgresql+asyncpg://clincore_user:@127.0.0.1/clincore')

async def main():
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text
    eng = create_async_engine(os.environ['DATABASE_URL'])
    async with eng.connect() as conn:
        # ساختار ستونها
        r = await conn.execute(text("""
            SELECT column_name, data_type, character_maximum_length
            FROM information_schema.columns
            WHERE table_name='shop_products'
            ORDER BY ordinal_position
        """))
        print("=COLUMNS=")
        for row in r.fetchall(): print(row)
        # نمونه داده
        r2 = await conn.execute(text("""
            SELECT name_fa, length(description), left(description,120)
            FROM shop_products LIMIT 3
        """))
        print("\n=SAMPLE DESC=")
        for row in r2.fetchall(): print(row)

asyncio.run(main())