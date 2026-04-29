import asyncio, os, sys, pathlib

env_path = pathlib.Path(r'D:\clincore-platform\.env')
for line in env_path.read_text(encoding='utf-8-sig').splitlines():
    line = line.strip()
    if line and not line.startswith('#') and '=' in line:
        k, v = line.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip())

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def main():
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text
    url = os.environ['DATABASE_URL']
    print('URL:', url[:50])
    eng = create_async_engine(url)
    async with eng.connect() as conn:
        r = await conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='shop_products' ORDER BY ordinal_position"
        ))
        print("COLS:", [row[0] for row in r.fetchall()])
        r2 = await conn.execute(text(
            "SELECT name_fa, length(description), left(description,150) "
            "FROM shop_products LIMIT 3"
        ))
        print("\nSAMPLE:")
        for row in r2.fetchall(): print(row)

asyncio.run(main())