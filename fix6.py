import pathlib, re

hp = pathlib.Path(r'D:\clincore-platform\src\clincore\templates\shop\index.html')
html = hp.read_text(encoding='utf-8')

# 1. کارت: "بیشتر" کلیکپذیر
OLD_CARD = '${p.description ? `<div class="card-desc">${p.description.slice(0,80)}${p.description.length>80?"...":""}</div>` : ""}'
NEW_CARD = '${p.description ? `<div class="card-desc">${p.description.slice(0,80)}${p.description.length>80?`... <span onclick="openProdDetail(\'${p.id}\')" style="color:var(--primary,#0d9488);cursor:pointer;font-weight:600;font-size:.78rem">بیشتر ▾</span>`:""}</div>` : `<div style="height:.5rem"></div>`}'

if 'openProdDetail' not in html:
    if OLD_CARD in html:
        html = html.replace(OLD_CARD, NEW_CARD)
        print('OK: card description patched')
    else:
        print('WARN: card desc pattern not found')
else:
    print('SKIP: already patched')

# 2. Modal توضیحات کامل + JS
MODAL = """
<div class="modal-overlay" id="prodDetailModal" onclick="if(event.target===this)closeProdDetail()" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:500;align-items:center;justify-content:center;padding:1rem;">
  <div style="background:var(--surface,#fff);border-radius:16px;width:100%;max-width:520px;max-height:85vh;overflow-y:auto;box-shadow:0 20px 60px rgba(0,0,0,.3);">
    <div style="padding:1.25rem 1.5rem;border-bottom:1px solid var(--border,#e5e7eb);display:flex;align-items:center;justify-content:space-between;">
      <div>
        <div id="pd-name" style="font-size:1.1rem;font-weight:700;"></div>
        <div id="pd-cat" style="font-size:.8rem;color:var(--muted,#6b7280);margin-top:2px;"></div>
      </div>
      <button onclick="closeProdDetail()" style="background:none;border:none;font-size:1.4rem;cursor:pointer;color:var(--muted,#6b7280);line-height:1;"></button>
    </div>
    <div style="padding:1.25rem 1.5rem;display:flex;flex-direction:column;gap:1rem;">
      <div style="display:flex;align-items:center;justify-content:space-between;">
        <div id="pd-price" style="font-size:1.2rem;font-weight:700;color:var(--primary,#0d9488);"></div>
        <div id="pd-badge"></div>
      </div>
      <div id="pd-desc-wrap" style="display:none;">
        <div style="font-size:.85rem;font-weight:600;color:var(--text,#111);margin-bottom:.5rem;padding-bottom:.4rem;border-bottom:1px solid var(--border,#e5e7eb);">📋 توضیحات محصول</div>
        <div id="pd-desc" style="font-size:.9rem;line-height:1.9;color:var(--text,#374151);white-space:pre-line;"></div>
      </div>
      <div id="pd-noDesc" style="font-size:.85rem;color:var(--muted,#6b7280);display:none;">توضیحاتی برای این محصول ثبت نشده است.</div>
      <button id="pd-addBtn" style="width:100%;padding:.75rem;border-radius:10px;border:none;background:var(--primary,#0d9488);color:#fff;font-size:1rem;font-weight:700;cursor:pointer;">افزودن به سبد خرید</button>
    </div>
  </div>
</div>
<script>
(function(){
  window.openProdDetail = function(id) {
    const p = (window.products||window.allProds||[]).find(x=>x.id===id);
    if(!p) return;
    document.getElementById('pd-name').textContent = p.name_fa || p.name;
    document.getElementById('pd-cat').textContent  = p.category;
    const pr = p.price.toLocaleString('fa-IR');
    document.getElementById('pd-price').textContent = pr + ' تومان / ' + p.unit;
    const stock = p.stock_quantity ?? 0;
    const thr   = p.stock_alert_threshold ?? 5;
    const bd    = document.getElementById('pd-badge');
    bd.innerHTML = stock<=0
      ? '<span style="background:#fee2e2;color:#dc2626;padding:3px 10px;border-radius:20px;font-size:.78rem;">ناموجود</span>'
      : stock<=thr
      ? '<span style="background:#fef3c7;color:#d97706;padding:3px 10px;border-radius:20px;font-size:.78rem;">موجودی کم</span>'
      : '<span style="background:#dcfce7;color:#16a34a;padding:3px 10px;border-radius:20px;font-size:.78rem;">موجود</span>';
    const dw = document.getElementById('pd-desc-wrap');
    const nd = document.getElementById('pd-noDesc');
    const dd = document.getElementById('pd-desc');
    if(p.description && p.description.trim()) {
      dd.textContent = p.description;
      dw.style.display='block'; nd.style.display='none';
    } else {
      dw.style.display='none'; nd.style.display='block';
    }
    const ab = document.getElementById('pd-addBtn');
    ab.disabled = stock<=0;
    ab.style.background = stock<=0 ? 'var(--muted,#9ca3af)' : 'var(--primary,#0d9488)';
    ab.onclick = stock<=0 ? null : function(){
      const sn=(p.name_fa||p.name).replace(/'/g,"\\'");
      if(typeof addToCart==='function') addToCart(p.id,sn,p.price,p.unit,stock);
      closeProdDetail();
    };
    const m = document.getElementById('prodDetailModal');
    m.style.display='flex';
    document.body.style.overflow='hidden';
  };
  window.closeProdDetail = function() {
    document.getElementById('prodDetailModal').style.display='none';
    document.body.style.overflow='';
  };
  document.addEventListener('keydown', e=>{ if(e.key==='Escape') closeProdDetail(); });
})();
</script>"""

if 'prodDetailModal' not in html:
    html = html.replace('</body>', MODAL + '\n</body>')
    print('OK: product detail modal added')
else:
    print('SKIP: modal already present')

# 3. expose products array to window
for pat in ['products = data.products', 'products = resp.products', 'allProds = data.products']:
    if pat in html and 'window.products' not in html:
        varname = pat.split('=')[0].strip()
        html = html.replace(pat, pat + f'; window.{varname} = {varname}')
        print(f'OK: window.{varname} exposed')
        break

hp.write_text(html, encoding='utf-8')
print('DONE - Ctrl+Shift+R on /shop')