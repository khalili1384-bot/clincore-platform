"""
ClinCore Admin Explorer — Deploy Script
Run from project root:
  python deploy_explorer.py
"""
import pathlib

BASE = pathlib.Path(r"D:\clincore-platform\src\clincore")

# ═══ 1. explorer_router.py ══════════════════════════════════════════════════
EXPLORER_ROUTER = '''\
"""Super Admin Explorer — serves the explorer HTML page."""
import pathlib
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["explorer"])

_HTML = pathlib.Path(__file__).resolve().parent.parent / "templates" / "explorer.html"


@router.get("/super-admin/explorer", response_class=HTMLResponse)
async def explorer_page():
    return HTMLResponse(content=_HTML.read_text(encoding="utf-8"))
'''

# ═══ 2. PATCH shop_product_router.py ════════════════════════════════════════
PATCH_PROD = '''

@router.patch("/shop/products/{product_id}")
async def update_product(
    product_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(_require_admin),
):
    tid = SHOP_TENANT_ID
    await db.execute(text(f"SET LOCAL app.tenant_id = \'{tid}\'"))
    safe_id = product_id.replace("\'", "\'\'")
    updates = []
    if "price" in body:
        updates.append(f"price = {float(body[\'price\'])}")
    if "stock_quantity" in body:
        updates.append(f"stock_quantity = {int(body[\'stock_quantity\'])}")
    if "stock_alert_threshold" in body:
        updates.append(f"stock_alert_threshold = {int(body[\'stock_alert_threshold\'])}")
    if "is_active" in body:
        val = "true" if body["is_active"] else "false"
        updates.append(f"is_active = {val}")
    if not updates:
        raise HTTPException(status_code=400, detail="\u0647\u06cc\u0686 \u0641\u06cc\u0644\u062f\u06cc \u0628\u0631\u0627\u06cc \u0628\u0647\u200c\u0631\u0648\u0632\u0631\u0633\u0627\u0646\u06cc \u0646\u06cc\u0633\u062a")
    updates.append("updated_at = NOW()")
    set_clause = ", ".join(updates)
    await db.execute(text(
        f"UPDATE shop_products SET {set_clause} "
        f"WHERE id = \'{safe_id}\' AND tenant_id = \'{tid}\'"
    ))
    await db.commit()
    return {"ok": True}
'''

# ═══ 3. main.py explorer block ══════════════════════════════════════════════
EXPLORER_BLOCK = """
    try:
        from clincore.shop.explorer_router import router as explorer_router
        app.include_router(explorer_router)
        logger.info("\\u2705 Explorer integrated")
    except ImportError as e:
        logger.warning("\\u26a0\\ufe0f Explorer skipped: %s", e)"""

# ════════════════════════════════════════════════════════════════════════════
p = BASE / "shop" / "explorer_router.py"
p.write_text(EXPLORER_ROUTER, encoding="utf-8")
print("1/4  explorer_router.py OK")

(BASE / "templates").mkdir(exist_ok=True)
html_p = BASE / "templates" / "explorer.html"
html_src = pathlib.Path(__file__).parent / "explorer.html"
import shutil; shutil.copy2(str(html_src), str(html_p))
print("2/4  explorer.html OK")

p = BASE / "clinical" / "shop_product_router.py"
t = p.read_text(encoding="utf-8")
if "@router.patch" not in t:
    p.write_text(t + PATCH_PROD, encoding="utf-8")
    print("3/4  shop_product_router.py patched (+PATCH)")
else:
    print("3/4  shop_product_router.py — already has PATCH, skip")

p = BASE / "api" / "main.py"
t = p.read_text(encoding="utf-8")
if "explorer_router" not in t:
    ANCHORS = [
        '    logger.info("\u2705 Super Admin integrated")',
        "    logger.info('\u2705 Super Admin integrated')",
    ]
    patched = False
    for anchor in ANCHORS:
        if anchor in t:
            p.write_text(t.replace(anchor, anchor + EXPLORER_BLOCK), encoding="utf-8")
            print("4/4  main.py patched")
            patched = True; break
    if not patched:
        print("WARN 4/4 anchor not found. Super-admin lines:")
        for i, l in enumerate(t.splitlines()):
            if "super" in l.lower() and ("admin" in l.lower() or "integrat" in l.lower()):
                print(f"  {i}: {repr(l)}")
else:
    print("4/4  main.py — already registered, skip")

print("\nDone! -> http://127.0.0.1:8000/super-admin/explorer")
