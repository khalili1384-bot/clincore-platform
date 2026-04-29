import pathlib, re

# ── 1. Backend: PATCH endpoint + description in admin-list ───────────────────
rp = pathlib.Path(r'D:\clincore-platform\src\clincore\clinical\shop_product_router.py')
txt = rp.read_text(encoding='utf-8')

# Fix admin-list to include description
OLD_SELECT = (
    'f"SELECT id, name, name_fa, category, price, unit, sku, "\n'
    '        f"is_active, stock_quantity, stock_alert_threshold "\n'
    '        f"FROM shop_products WHERE tenant_id = \'{tid}\' ORDER BY category, name_fa"'
)
NEW_SELECT = (
    'f"SELECT id, name, name_fa, category, description, price, unit, sku, "\n'
    '        f"is_active, stock_quantity, stock_alert_threshold "\n'
    '        f"FROM shop_products WHERE tenant_id = \'{tid}\' ORDER BY category, name_fa"'
)
if 'description' not in txt[txt.find('admin-list'):txt.find('admin-list')+600]:
    if OLD_SELECT in txt:
        txt = txt.replace(OLD_SELECT, NEW_SELECT)
        print('OK: description added to admin-list')
    else:
        print('WARN: admin-list SELECT pattern not found - check manually')
else:
    print('SKIP: admin-list already has description')

# Also fix the products dict in admin-list to include description
OLD_DICT = '"low_stock": 0 < qty <= thr, "out_of_stock": qty <= 0,'
NEW_DICT = '"description": r.description or "", "low_stock": 0 < qty <= thr, "out_of_stock": qty <= 0,'
if '"description"' not in txt[txt.find('admin-list'):txt.find('admin-list')+900]:
    if OLD_DICT in txt:
        txt = txt.replace(OLD_DICT, NEW_DICT)
        print('OK: description field added to admin-list response')
else:
    print('SKIP: description already in response dict')

# Add PATCH endpoint
PATCH_EP = '''

@router.patch("/shop/products/{product_id}")
async def patch_product(
    product_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(_require_admin),
):
    tid = SHOP_TENANT_ID
    await db.execute(text(f"SET LOCAL app.tenant_id = \'{tid}\'"))
    def esc(v): return str(v or "").replace("\'", "\'\'")
    sid = product_id.replace("\'", "\'\'")
    sets = []
    if "name"     in body: sets.append(f"name=\'{esc(body[\'name\'])}\'")
    if "name_fa"  in body: sets.append(f"name_fa=\'{esc(body[\'name_fa\'])}\'")
    if "category" in body: sets.append(f"category=\'{esc(body[\'category\'])}\'")
    if "description" in body:
        d = esc(body["description"])
        sets.append(f"description=\'{d}\'" if d else "description=NULL")
    if "price"    in body: sets.append(f"price={float(body[\'price\'])}")
    if "unit"     in body: sets.append(f"unit=\'{esc(body[\'unit\'])}\'")
    if "sku"      in body:
        s = esc(body["sku"])
        sets.append(f"sku=\'{s}\'" if s else "sku=NULL")
    if "stock_quantity"       in body: sets.append(f"stock_quantity={int(body[\'stock_quantity\'])}")
    if "stock_alert_threshold" in body: sets.append(f"stock_alert_threshold={int(body[\'stock_alert_threshold\'])}")
    if "is_active" in body:
        ia = "true" if body["is_active"] else "false"
        sets.append(f"is_active={ia}")
    if not sets:
        raise HTTPException(status_code=422, detail="no fields to update")
    sets.append("updated_at=NOW()")
    set_clause = ", ".join(sets)
    r = await db.execute(text(
        f"UPDATE shop_products SET {set_clause} "
        f"WHERE id=\'{sid}\' AND tenant_id=\'{tid}\'"
    ))
    await db.commit()
    if r.rowcount == 0: raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}
'''

if 'patch_product' not in txt:
    txt += PATCH_EP
    print('OK: PATCH endpoint added')
else:
    print('SKIP: PATCH already exists')

rp.write_text(txt, encoding='utf-8')

# ── 2. Frontend: Edit modal + JS ─────────────────────────────────────────────
hp = pathlib.Path(r'D:\clincore-platform\src\clincore\templates\explorer.html')
html = hp.read_text(encoding='utf-8')

# Add edit button to row template
OLD_ROW = "onclick=\"saveProduct('${p.id}', this)\">💾 ذخیره</button><button class=\"btn btn-danger btn-sm\" style=\"margin-right:4px\" onclick=\"deleteProd('${p.id}',this)\">🗑 حذف</button>"
NEW_ROW = OLD_ROW + "<button class=\"btn btn-sm\" style=\"background:#1e40af;color:#bfdbfe;border:1px solid #1d4ed8;border-radius:4px;padding:2px 8px;cursor:pointer;font-size:12px;margin-right:4px\" onclick=\"openEditModal('${p.id}')\">✏️ ویرایش</button>"

if 'openEditModal' not in html:
    if OLD_ROW in html:
        html = html.replace(OLD_ROW, NEW_ROW)
        print('OK: edit button added to row')
    else:
        print('WARN: row pattern not found')
else:
    print('SKIP: edit button already present')

EDIT_MODAL = """
<!-- EDIT PRODUCT MODAL -->
<div id="modal-edit-prod" onclick="if(event.target===this)closeEditModal()"
  style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.65);z-index:10000;align-items:center;justify-content:center;">
  <div style="background:#1c2030;border:1px solid #2a3040;border-radius:12px;padding:28px;width:600px;max-width:96vw;max-height:90vh;overflow-y:auto;box-shadow:0 12px 40px rgba(0,0,0,.6);">
    <h3 style="margin:0 0 18px;font-size:15px;color:#dde3f0;">✏️ ویرایش محصول</h3>
    <input type="hidden" id="ep-id">
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
      <div><label style="font-size:11px;color:#889;display:block;margin-bottom:3px;">نام فارسی *</label>
        <input id="ep-fa" style="width:100%;padding:7px 9px;background:#252b3b;border:1px solid #2a3040;border-radius:6px;color:#dde3f0;font-size:13px;box-sizing:border-box;"></div>
      <div><label style="font-size:11px;color:#889;display:block;margin-bottom:3px;">نام انگلیسی *</label>
        <input id="ep-name" style="width:100%;padding:7px 9px;background:#252b3b;border:1px solid #2a3040;border-radius:6px;color:#dde3f0;font-size:13px;box-sizing:border-box;"></div>
      <div><label style="font-size:11px;color:#889;display:block;margin-bottom:3px;">دستهبندی *</label>
        <input id="ep-cat" style="width:100%;padding:7px 9px;background:#252b3b;border:1px solid #2a3040;border-radius:6px;color:#dde3f0;font-size:13px;box-sizing:border-box;"></div>
      <div><label style="font-size:11px;color:#889;display:block;margin-bottom:3px;">قیمت (ریال) *</label>
        <input id="ep-price" type="number" min="0" style="width:100%;padding:7px 9px;background:#252b3b;border:1px solid #2a3040;border-radius:6px;color:#dde3f0;font-size:13px;box-sizing:border-box;"></div>
      <div><label style="font-size:11px;color:#889;display:block;margin-bottom:3px;">واحد</label>
        <input id="ep-unit" style="width:100%;padding:7px 9px;background:#252b3b;border:1px solid #2a3040;border-radius:6px;color:#dde3f0;font-size:13px;box-sizing:border-box;"></div>
      <div><label style="font-size:11px;color:#889;display:block;margin-bottom:3px;">SKU</label>
        <input id="ep-sku" style="width:100%;padding:7px 9px;background:#252b3b;border:1px solid #2a3040;border-radius:6px;color:#dde3f0;font-size:13px;box-sizing:border-box;"></div>
    </div>
    <div style="margin-top:10px;">
      <label style="font-size:11px;color:#889;display:block;margin-bottom:3px;">توضیحات محصول (برای مشتری)</label>
      <textarea id="ep-desc" rows="5" placeholder="روش استفاده موارد کاربرد ترکیبات و هر اطلاعاتی که مشتری باید بداند..." style="width:100%;padding:8px 9px;background:#252b3b;border:1px solid #2a3040;border-radius:6px;color:#dde3f0;font-size:13px;box-sizing:border-box;resize:vertical;line-height:1.7;font-family:inherit;"></textarea>
    </div>
    <div id="ep-err" style="color:#f87171;font-size:12px;margin-top:8px;display:none;padding:7px 10px;background:rgba(248,113,113,.1);border-radius:5px;"></div>
    <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:20px;">
      <button onclick="closeEditModal()" style="padding:7px 18px;border-radius:6px;border:1px solid #2a3040;background:transparent;color:#889;cursor:pointer;font-size:13px;">انصراف</button>
      <button onclick="submitEditModal()" id="ep-submit" style="padding:7px 20px;border-radius:6px;border:none;background:#1d4ed8;color:#fff;cursor:pointer;font-size:13px;font-weight:600;">💾 ذخیره</button>
    </div>
  </div>
</div>
<script>
window.openEditModal = function(id) {
  const p = (window.allProducts||[]).find(x=>x.id===id);
  if(!p){ alert('محصول یافت نشد'); return; }
  document.getElementById('ep-id').value    = p.id;
  document.getElementById('ep-fa').value    = p.name_fa   || '';
  document.getElementById('ep-name').value  = p.name      || '';
  document.getElementById('ep-cat').value   = p.category  || '';
  document.getElementById('ep-price').value = p.price     || 0;
  document.getElementById('ep-unit').value  = p.unit      || 'عدد';
  document.getElementById('ep-sku').value   = p.sku       || '';
  document.getElementById('ep-desc').value  = p.description|| '';
  document.getElementById('ep-err').style.display = 'none';
  document.getElementById('modal-edit-prod').style.display = 'flex';
  setTimeout(()=>document.getElementById('ep-fa').focus(), 50);
};
window.closeEditModal = function() {
  document.getElementById('modal-edit-prod').style.display = 'none';
};
window.submitEditModal = async function() {
  const err = document.getElementById('ep-err'); err.style.display='none';
  const sb  = document.getElementById('ep-submit');
  const id  = document.getElementById('ep-id').value;
  const name_fa  = document.getElementById('ep-fa').value.trim();
  const name     = document.getElementById('ep-name').value.trim();
  const category = document.getElementById('ep-cat').value.trim();
  const price    = parseFloat(document.getElementById('ep-price').value)||0;
  const unit     = document.getElementById('ep-unit').value.trim()||'عدد';
  const sku      = document.getElementById('ep-sku').value.trim();
  const description = document.getElementById('ep-desc').value.trim();
  if(!name_fa||!name||!category){
    err.textContent='نام فارسی انگلیسی و دستهبندی الزامی است.';
    err.style.display='block'; return;
  }
  sb.disabled=true; sb.textContent='...';
  try {
    await apiFetch('/shop/products/'+id, {method:'PATCH',
      body: JSON.stringify({name_fa,name,category,price,unit,sku,description})
    });
    const p = (window.allProducts||[]).find(x=>x.id===id);
    if(p) Object.assign(p,{name_fa,name,category,price,unit,sku,description});
    if(typeof renderProducts==='function') renderProducts();
    closeEditModal();
    if(typeof toast==='function') toast('محصول ویرایش شد ✓','ok');
  } catch(e) {
    err.textContent=e.message; err.style.display='block';
  } finally { sb.disabled=false; sb.textContent='💾 ذخیره'; }
};
document.addEventListener('keydown', e=>{ if(e.key==='Escape') closeEditModal(); });
</script>
<!-- END EDIT PRODUCT MODAL -->"""

if 'modal-edit-prod' not in html:
    html = html.replace('</body>', EDIT_MODAL + '\n</body>')
    print('OK: edit modal injected')
else:
    print('SKIP: edit modal already present')

hp.write_text(html, encoding='utf-8')
print('DONE — Ctrl+Shift+R in browser')