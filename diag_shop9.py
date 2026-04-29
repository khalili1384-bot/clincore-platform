import asyncio, os, sys, pathlib

for line in pathlib.Path(r'D:\clincore-platform\.env').read_text(encoding='utf-8-sig').splitlines():
    line = line.strip()
    if line and not line.startswith('#') and '=' in line:
        k, v = line.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip())

SHOP_TID = 'c5e65972-36eb-42c6-ac46-8740593171bc'

async def main():
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text
    eng = create_async_engine(os.environ['DATABASE_URL'])
    async with eng.begin() as conn:
        await conn.execute(text(f"SET LOCAL app.tenant_id = '{SHOP_TID}'"))
        r = await conn.execute(text(
            f"SELECT name_fa, length(description) as dlen, left(description,200) "
            f"FROM shop_products WHERE tenant_id='{SHOP_TID}' LIMIT 5"
        ))
        rows = r.fetchall()
        print(f'TOTAL ROWS: {len(rows)}')
        for row in rows:
            print(f'  name={row[0]} | desc_len={row[1]} | preview={row[2]}')

asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)