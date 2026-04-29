# ═══════════════════════════════════════════════════════════════════
# ClinCore — Shop Admin Patch
# افزودن POST (محصول جدید) + DELETE (حذف محصول)
# اجرا: .\patch_shop.ps1
# ═══════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Stop"

# ── STEP 1: Backend ─────────────────────────────────────────────────
$rp = "D:\clincore-platform\src\clincore\clinical\shop_product_router.py"
$txt = [IO.File]::ReadAllText($rp, [Text.Encoding]::UTF8)

if ($txt -notmatch "create_product") {
    $add = @'


@router.post("/shop/products")
async def create_product(
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(_require_admin),
):
    tid = SHOP_TENANT_ID
    await db.execute(text(f"SET LOCAL app.tenant_id = '{tid}'"))
    import uuid; pid = str(uuid.uuid4())
    def esc(v): return str(v or "").replace("'", "''")
    name  = esc(body.get("name",  ""));  name_fa = esc(body.get("name_fa", ""))
    cat   = esc(body.get("category", "")); desc  = esc(body.get("description", ""))
    unit  = esc(body.get("unit", "عدد")); sku    = esc(body.get("sku", ""))
    price = float(body.get("price", 0)); stock   = int(body.get("stock_quantity", 0))
    thr   = int(body.get("stock_alert_threshold", 5))
    ia    = "true" if body.get("is_active", True) else "false"
    d_sql = f"'{desc}'" if desc else "NULL"
    s_sql = f"'{sku}'"  if sku  else "NULL"
    if not name or not name_fa or not cat:
        raise HTTPException(status_code=422, detail="name, name_fa, category required")
    await db.execute(text(
        f"INSERT INTO shop_products "
        f"(id,tenant_id,name,name_fa,category,description,"
        f"price,unit,sku,stock_quantity,stock_alert_threshold,is_active,created_at,updated_at) "
        f"VALUES ('{pid}','{tid}','{name}','{name_fa}','{cat}',"
        f"{d_sql},{price},'{unit}',{s_sql},{stock},{thr},{ia},NOW(),NOW())"
    ))
    await db.commit()
    return {"ok": True, "id": pid}


@router.delete("/shop/products/{product_id}")
async def delete_product(
    product_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(_require_admin),
):
    tid = SHOP_TENANT_ID
    await db.execute(text(f"SET LOCAL app.tenant_id = '{tid}'"))
    sid = product_id.replace("'", "''")
    r = await db.execute(text(
        f"DELETE FROM shop_products WHERE id='{sid}' AND tenant_id='{tid}'"
    ))
    await db.commit()
    if r.rowcount == 0: raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}
'@
    [IO.File]::WriteAllText($rp, $txt + $add, [Text.Encoding]::UTF8)
    Write-Host "✅ Backend: POST + DELETE اضافه شد" -ForegroundColor Green
} else {
    Write-Host "⏭  Backend: قبلاً پچ شده" -ForegroundColor Yellow
}

# ── STEP 2: Frontend ─────────────────────────────────────────────────
$htmlPath = (Get-ChildItem -Path D:\clincore-platform -Recurse -Filter "explorer.html" `
             -ErrorAction SilentlyContinue | Select-Object -First 1).FullName

if (-not $htmlPath) {
    Write-Host "⚠️  explorer.html پیدا نشد — مسیر HTML پنل را مستقیم وارد کنید:" -ForegroundColor Yellow
    $htmlPath = Read-Host "مسیر کامل فایل HTML"
}

if ($htmlPath -and (Test-Path $htmlPath)) {
    $html = [IO.File]::ReadAllText($htmlPath, [Text.Encoding]::UTF8)

    if ($html -notmatch "modal-new-prod") {
        $inject = @'

<!-- ═══════ CLINCORE SHOP PATCH — ADD+DELETE ═══════ -->
<div id="modal-new-prod" onclick="if(event.target===this)closeNewProd()"
  style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.65);z-index:9999;align-items:center;justify-content:center;">
  <div style="background:#1c2030;border:1px solid #2a3040;border-radius:12px;padding:28px;width:540px;max-width:96vw;box-shadow:0 12px 40px rgba(0,0,0,.6);">
    <h3 style="margin:0 0 18px;font-size:15px;color:#dde3f0;">➕ محصول جدید</h3>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
      <div><label style="font-size:11px;color:#889;display:block;margin-bottom:3px;">نام انگلیسی *</label>
           <input id="np-name" placeholder="Arsenicum album" style="width:100%;padding:7px 9px;background:#252b3b;border:1px solid #2a3040;border-radius:6px;color:#dde3f0;font-size:13px;box-sizing:border-box;"></div>
      <div><label style="font-size:11px;color:#889;display:block;margin-bottom:3px;">نام فارسی *</label>
           <input id="np-fa" placeholder="آرسنیکوم آلبوم" style="width:100%;padding:7px 9px;background:#252b3b;border:1px solid #2a3040;border-radius:6px;color:#dde3f0;font-size:13px;box-sizing:border-box;"></div>
      <div><label style="font-size:11px;color:#889;display:block;margin-bottom:3px;">دسته‌بندی *</label>
           <input id="np-cat" placeholder="Remedies" style="width:100%;padding:7px 9px;background:#252b3b;border:1px solid #2a3040;border-radius:6px;color:#dde3f0;font-size:13px;box-sizing:border-box;"></div>
      <div><label style="font-size:11px;color:#889;display:block;margin-bottom:3px;">قیمت (ریال) *</label>
           <input id="np-price" type="number" min="0" placeholder="150000" style="width:100%;padding:7px 9px;background:#252b3b;border:1px solid #2a3040;border-radius:6px;color:#dde3f0;font-size:13px;box-sizing:border-box;"></div>
      <div><label style="font-size:11px;color:#889;display:block;margin-bottom:3px;">واحد</label>
           <input id="np-unit" value="عدد" style="width:100%;padding:7px 9px;background:#252b3b;border:1px solid #2a3040;border-radius:6px;color:#dde3f0;font-size:13px;box-sizing:border-box;"></div>
      <div><label style="font-size:11px;color:#889;display:block;margin-bottom:3px;">SKU (اختیاری)</label>
           <input id="np-sku" placeholder="" style="width:100%;padding:7px 9px;background:#252b3b;border:1px solid #2a3040;border-radius:6px;color:#dde3f0;font-size:13px;box-sizing:border-box;"></div>
      <div><label style="font-size:11px;color:#889;display:block;margin-bottom:3px;">موجودی اولیه</label>
           <input id="np-stock" type="number" value="0" style="width:100%;padding:7px 9px;background:#252b3b;border:1px solid #2a3040;border-radius:6px;color:#dde3f0;font-size:13px;box-sizing:border-box;"></div>
      <div><label style="font-size:11px;color:#889;display:block;margin-bottom:3px;">حد هشدار کمبود</label>
           <input id="np-thr" type="number" value="5" style="width:100%;padding:7px 9px;background:#252b3b;border:1px solid #2a3040;border-radius:6px;color:#dde3f0;font-size:13px;box-sizing:border-box;"></div>
      <div style="grid-column:span 2">
           <label style="font-size:11px;color:#889;display:block;margin-bottom:3px;">توضیحات (اختیاری)</label>
           <input id="np-desc" style="width:100%;padding:7px 9px;background:#252b3b;border:1px solid #2a3040;border-radius:6px;color:#dde3f0;font-size:13px;box-sizing:border-box;"></div>
    </div>
    <div id="np-err" style="color:#f87171;font-size:12px;margin-top:8px;display:none;padding:7px 10px;background:rgba(248,113,113,.1);border-radius:5px;"></div>
    <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:20px;">
      <button onclick="closeNewProd()" style="padding:7px 18px;border-radius:6px;border:1px solid #2a3040;background:transparent;color:#889;cursor:pointer;font-size:13px;">انصراف</button>
      <button onclick="submitNewProd()" id="np-submit" style="padding:7px 20px;border-radius:6px;border:none;background:#4f8ef7;color:#fff;cursor:pointer;font-size:13px;font-weight:600;">💾 ذخیره</button>
    </div>
  </div>
</div>

<script>
(function(){
  /* ── key/url detection ──────────────────────────────────────────── */
  function _base(){
    if(typeof API_BASE!=='undefined')return API_BASE;
    if(typeof BASE!=='undefined')return BASE;
    var m=document.documentElement.innerHTML.match(/https?:\/\/127\.0\.0\.1:\d+/);
    return m?m[0]:'http://127.0.0.1:8000';
  }
  function _akey(){
    if(typeof SUPER_ADMIN_KEY!=='undefined')return SUPER_ADMIN_KEY;
    if(typeof ADMIN_KEY!=='undefined')return ADMIN_KEY;
    var ss=document.querySelectorAll('script:not([src])');
    for(var i=0;i<ss.length;i++){
      var m=ss[i].textContent.match(/['"]X-Super-Admin-Key['"]\s*:\s*['"]([^'"]+)['"]/);
      if(m)return m[1];
      m=ss[i].textContent.match(/(?:SUPER_ADMIN|ADMIN)_KEY\s*=\s*['"]([^'"]+)['"]/);
      if(m)return m[1];
    }
    return '';
  }

  /* ── inject "New Product" button ────────────────────────────────── */
  function injectBtn(){
    if(document.getElementById('_np_btn'))return;
    var reloadBtn=null;
    var btns=document.querySelectorAll('button');
    for(var i=0;i<btns.length;i++){
      var b=btns[i];
      if((b.id&&/reload.product/i.test(b.id))||
         (b.onclick&&/loadProduct|reloadProduct/i.test(b.onclick.toString()))||
         /بروزرسانی|refresh/i.test(b.textContent)){
        reloadBtn=b;break;
      }
    }
    if(!reloadBtn){setTimeout(injectBtn,700);return;}
    var btn=document.createElement('button');
    btn.id='_np_btn';
    btn.textContent='➕ محصول جدید';
    var cs=window.getComputedStyle(reloadBtn);
    btn.style.cssText='padding:'+cs.padding+';border-radius:'+cs.borderRadius+
      ';border:none;background:#4f8ef7;color:#fff;cursor:pointer;'+
      'font-size:'+cs.fontSize+';margin-right:6px;font-weight:600;';
    btn.onclick=function(){openNewProd();};
    reloadBtn.parentNode.insertBefore(btn,reloadBtn);
  }

  /* ── MutationObserver: add 🗑 button to every new product row ──── */
  var obs=new MutationObserver(function(){
    document.querySelectorAll('tbody tr:not([data-del-ok])').forEach(function(tr){
      var id=tr.dataset.id||tr.dataset.productId||'';
      if(!id){
        for(var c=0;c<Math.min(tr.cells.length,3);c++){
          var v=(tr.cells[c]?tr.cells[c].textContent:'').trim();
          if(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}/.test(v)){id=v;break;}
        }
      }
      if(!id)return;
      tr.dataset.delOk='1';
      var last=tr.cells[tr.cells.length-1];
      if(!last)return;
      var d=document.createElement('button');
      d.textContent='🗑';d.title='حذف محصول';
      d.style.cssText='background:#7f1d1d;color:#fca5a5;border:1px solid #991b1b;'+
        'border-radius:4px;padding:2px 8px;cursor:pointer;font-size:13px;margin-left:4px;';
      d.onmouseover=function(){this.style.background='#991b1b';};
      d.onmouseout =function(){this.style.background='#7f1d1d';};
      d.onclick=function(){deleteProd(id,tr);};
      last.appendChild(d);
    });
  });
  obs.observe(document.body,{childList:true,subtree:true});

  /* ── modal open/close ───────────────────────────────────────────── */
  window.openNewProd=function(){
    var m=document.getElementById('modal-new-prod');
    m.style.display='flex';
    document.getElementById('np-err').style.display='none';
    setTimeout(function(){document.getElementById('np-name').focus();},50);
  };
  window.closeNewProd=function(){
    document.getElementById('modal-new-prod').style.display='none';
  };
  document.addEventListener('keydown',function(e){
    if(e.key==='Escape')closeNewProd();
  });

  /* ── submit new product ─────────────────────────────────────────── */
  window.submitNewProd=async function(){
    var err=document.getElementById('np-err');
    err.style.display='none';
    var sb=document.getElementById('np-submit');
    var name   =document.getElementById('np-name').value.trim();
    var name_fa=document.getElementById('np-fa').value.trim();
    var cat    =document.getElementById('np-cat').value.trim();
    var price  =parseFloat(document.getElementById('np-price').value)||0;
    var unit   =document.getElementById('np-unit').value.trim()||'عدد';
    var sku    =document.getElementById('np-sku').value.trim();
    var desc   =document.getElementById('np-desc').value.trim();
    var stock  =parseInt(document.getElementById('np-stock').value)||0;
    var thr    =parseInt(document.getElementById('np-thr').value)||5;
    if(!name||!name_fa||!cat){
      err.textContent='نام انگلیسی، فارسی و دسته‌بندی الزامی است.';
      err.style.display='block';return;
    }
    var akey=_akey();
    if(!akey)akey=prompt('X-Super-Admin-Key:')||'';
    sb.disabled=true;sb.textContent='...';
    try{
      var r=await fetch(_base()+'/shop/products',{
        method:'POST',
        headers:{'Content-Type':'application/json','X-Super-Admin-Key':akey},
        body:JSON.stringify({name:name,name_fa:name_fa,category:cat,price:price,
          unit:unit,sku:sku,description:desc,stock_quantity:stock,
          stock_alert_threshold:thr,is_active:true})
      });
      if(!r.ok){var t=await r.text();throw new Error(r.status+' '+t);}
      closeNewProd();
      ['np-name','np-fa','np-cat','np-price','np-sku','np-desc'].forEach(function(id){
        document.getElementById(id).value='';
      });
      document.getElementById('np-stock').value='0';
      document.getElementById('np-thr').value='5';
      if(typeof loadProducts==='function')loadProducts();
      else if(typeof reloadProducts==='function')reloadProducts();
      else location.reload();
    }catch(e){err.textContent=e.message;err.style.display='block';}
    finally{sb.disabled=false;sb.textContent='💾 ذخیره';}
  };

  /* ── delete product ─────────────────────────────────────────────── */
  window.deleteProd=async function(id,tr){
    if(!confirm('محصول حذف شود؟\nاین عمل قابل برگشت نیست.'))return;
    var akey=_akey();
    if(!akey)akey=prompt('X-Super-Admin-Key:')||'';
    var btn=tr.querySelector('button[title="حذف محصول"]');
    if(btn)btn.disabled=true;
    try{
      var r=await fetch(_base()+'/shop/products/'+id,{
        method:'DELETE',headers:{'X-Super-Admin-Key':akey}
      });
      if(!r.ok){var t=await r.text();throw new Error(r.status+' '+t);}
      tr.style.transition='opacity .3s,transform .3s';
      tr.style.opacity='0';tr.style.transform='translateX(20px)';
      setTimeout(function(){tr.remove();},300);
    }catch(e){alert('خطا: '+e.message);if(btn)btn.disabled=false;}
  };

  /* ── init ───────────────────────────────────────────────────────── */
  if(document.readyState==='loading')
    document.addEventListener('DOMContentLoaded',injectBtn);
  else setTimeout(injectBtn,400);
})();
</script>
<!-- ═══════ END CLINCORE SHOP PATCH ═══════ -->
