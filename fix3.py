import pathlib

hp = pathlib.Path(r'D:\clincore-platform\src\clincore\templates\explorer.html')
html = hp.read_text(encoding='utf-8')

print('SIZE:', len(html))
print('HAS_PATCH:', 'modal-new-prod' in html)

OLD1 = 'id="btn-reload-products">🔄 بروزرسانی</button>'
NEW1 = 'id="btn-reload-products">🔄 بروزرسانی</button>\n        <button class="btn btn-primary btn-sm" onclick="openNewProd()">➕ محصول جدید</button>'

OLD2 = "onclick=\"saveProduct('${p.id}', this)\">💾 ذخیره</button>"
NEW2 = "onclick=\"saveProduct('${p.id}', this)\">💾 ذخیره</button><button class=\"btn btn-danger btn-sm\" style=\"margin-right:4px\" onclick=\"deleteProd('${p.id}',this)\">🗑 حذف</button>"

MODAL_ALREADY = 'modal-new-prod' in html

if OLD1 in html:
    html = html.replace(OLD1, NEW1)
    print('OK: + button added')
else:
    print('WARN: reload btn not found')

if OLD2 in html:
    html = html.replace(OLD2, NEW2)
    print('OK: delete btn added')
else:
    print('WARN: save btn not found')

if not MODAL_ALREADY:
    import pathlib as _p
    old_src = _p.Path(r'D:\clincore-platform\explorer.html').read_text(encoding='utf-8')
    import re
    modal_block = re.search(r'<!-- CLINCORE SHOP PATCH.*?<!-- END CLINCORE SHOP PATCH -->', old_src, re.S)
    if modal_block:
        html = html.replace('</body>', modal_block.group(0) + '\n</body>')
        print('OK: modal injected from root explorer.html')
    else:
        print('WARN: modal block not found in root file')
else:
    print('SKIP: modal already present')

hp.write_text(html, encoding='utf-8')
print('DONE - now Ctrl+Shift+R in browser')