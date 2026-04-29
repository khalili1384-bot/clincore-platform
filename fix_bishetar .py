import pathlib

SRC = pathlib.Path(r'D:\clincore-platform\src\templates\shop\index.html')
c = SRC.read_text(encoding='utf-8')

CSS = '''
.more-link{color:var(--teal);font-size:.75rem;cursor:pointer;background:none;border:none;font-family:inherit;padding:0;display:inline;text-decoration:underline dotted}
.more-link:hover{color:var(--teal-dark)}
.prod-overlay{position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:400;display:flex;align-items:center;justify-content:center;padding:1rem;opacity:0;pointer-events:none;transition:.25s}
.prod-overlay.open{opacity:1;pointer-events:all}
.prod-box{background:var(--surface);border-radius:16px;width:100%;max-width:520px;max-height:88vh;overflow-y:auto;transform:translateY(12px);transition:.25s;display:flex;flex-direction:column}
.prod-overlay.open .prod-box{transform:translateY(0)}
.prod-head{padding:1.25rem 1.5rem;border-bottom:1px solid var(--border);display:flex;align-items:flex-start;justify-content:space-between;gap:1rem}
.prod-head h2{font-size:1.05rem;font-weight:700;line-height:1.4}
.prod-body{padding:1.5rem;display:flex;flex-direction:column;gap:1rem;flex:1}
.prod-row{display:flex;gap:.5rem;font-size:.85rem}
.prod-row strong{color:var(--muted);min-width:80px;flex-shrink:0}
.prod-desc-full{font-size:.88rem;color:var(--text);line-height:1.85;white-space:pre-wrap;background:var(--bg);border-radius:8px;padding:1rem}
.prod-foot{padding:1rem 1.5rem;border-top:1px solid var(--border);display:flex;gap:.75rem}
'''

MODAL = '''
<div class="prod-overlay" id="prodOverlay" onclick="closeProd(event)">
  <div class="prod-box">
    <div class="prod-head">
      <h2 id="pm-name"></h2>
      <button class="close-btn" onclick="document.getElementById('prodOverlay').classList.remove('open')">&#x2715;</button>
    </div>
    <div class="prod-body">
      <div class="prod-row"><strong>دسته:</strong><span id="pm-cat"></span></div>
      <div class="prod-row"><strong>قیمت:</strong><span id="pm-price"></span></div>
      <div class="prod-row"><strong>موجودی:</strong><span id="pm-stock"></span></div>
      <div id="pm-desc-wrap" style="display:none">
        <div style="font-size:.8rem;font-weight:700;color:var(--muted);margin-bottom:.5rem">توضیحات کامل</div>
        <div class="prod-desc-full" id="pm-desc"></div>
      </div>
    </div>
    <div class="prod-foot">
      <button class="btn-secondary" onclick="document.getElementById('prodOverlay').classList.remove('open')">بستن</button>
      <button class="btn-primary" id="pm-add" onclick="pmAdd()">افزودن به سبد</button>
    </div>
  </div>
</div>
'''

JS = '''
var _pm = null;
function openProd(pid) {
  var p = allProducts.find(function(x){return x.id===pid;});
  if(!p) return;
  _pm = p;
  document.getElementById('pm-name').textContent = p.name_fa||p.name;
  document.getElementById('pm-cat').textContent  = p.category;
  document.getElementById('pm-price').textContent = p.price.toLocaleString('fa-IR')+' تومان / '+p.unit;
  var s=p.stock_quantity||0, t=p.stock_alert_threshold||5;
  document.getElementById('pm-stock').textContent = s<=0?'ناموجود':s<=t?('موجودی کم ('+s+')'):'موجود';
  var w=document.getElementById('pm-desc-wrap');
  if(p.description){document.getElementById('pm-desc').textContent=p.description;w.style.display='';}
  else{w.style.display='none';}
  var b=document.getElementById('pm-add');
  b.disabled=s<=0; b.textContent=s<=0?'ناموجود':'افزودن به سبد';
  document.getElementById('prodOverlay').classList.add('open');
}
function closeProd(e){
  if(e.target===document.getElementById('prodOverlay'))
    document.getElementById('prodOverlay').classList.remove('open');
}
function pmAdd(){
  if(!_pm)return;
  addToCart(_pm.id,_pm.name_fa||_pm.name,_pm.price,_pm.unit,_pm.stock_quantity||0);
  document.getElementById('prodOverlay').classList.remove('open');
}
document.addEventListener('click',function(e){
  var b=e.target.classList.contains('more-link')?e.target:null;
  if(!b)return;
  var c=b.parentElement;
  while(c&&!c.classList.contains('card'))c=c.parentElement;
  if(!c)return;
  var ab=c.querySelector('.add-btn');
  if(!ab)return;
  var oc=ab.getAttribute('onclick')||'';
  var found=oc.match(/([0-9a-f]{8}.[0-9a-f]{4}.[0-9a-f]{4}.[0-9a-f]{4}.[0-9a-f]{12})/);
  if(found)openProd(found[1]);
});
'''

if '.prod-overlay' not in c:
    c = c.replace('</style>', CSS + '</style>', 1)
    print('OK css')
else: print('-- css exists')

if 'prodOverlay' not in c:
    c = c.replace('</body>', MODAL + '</body>', 1)
    print('OK modal')
else: print('-- modal exists')

if 'function openProd(' not in c:
    idx = c.rfind('</script>')
    c = c[:idx] + JS + c[idx:]
    print('OK js')
else: print('-- js exists')

if 'more-link' not in c:
    OLD = 'p.description.length>80?"...":""'
    Q = chr(34)
    NEW = 'p.description.length>80?'+Q+'... <button class='+chr(92)+Q+'more-link'+chr(92)+Q+'>بیشتر</button>'+Q+':'+Q+Q
    if OLD in c:
        c = c.replace(OLD, NEW, 1)
        print('OK more-link')
    else:
        print('WARN desc pattern not found')
        i = c.find('card-desc')
        if i>=0: print(repr(c[i:i+300]))
else: print('-- more-link exists')

SRC.write_text(c, encoding='utf-8')
print('DONE')