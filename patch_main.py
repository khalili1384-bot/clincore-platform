import pathlib

p = pathlib.Path(r"D:\clincore-platform\src\clincore\api\main.py")
t = p.read_text(encoding="utf-8")

old = "    from clincore.clinical.shop_product_router import router as shop_router\n    app.include_router(shop_router)"
new = "    from clincore.clinical.shop_product_router import router as shop_product_router\n    from clincore.shop.orders_router import router as shop_orders_router\n    from clincore.shop.shop_router import router as shop_pages_router\n    app.include_router(shop_product_router)\n    app.include_router(shop_orders_router)\n    app.include_router(shop_pages_router)"

if old in t:
    p.write_text(t.replace(old, new), encoding="utf-8")
    print("PATCHED OK")
else:
    print("NOT FOUND")
    for i, l in enumerate(t.splitlines()):
        if "shop" in l.lower() and ("router" in l or "include" in l):
            print(i, repr(l))