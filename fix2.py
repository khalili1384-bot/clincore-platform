import pathlib

hp = pathlib.Path(r'D:\clincore-platform\explorer.html')
html = hp.read_text(encoding='utf-8')

# 1. دکمه محصول جدید کنار reload
OLD1 = 'id="btn-reload-products">🔄 بروزرسانی</button>'
NEW1 = 'id="btn-reload-products">🔄 بروزرسانی</button>\n        <button class="btn btn-primary btn-sm" onclick="openNewProd()">➕ محصول جدید</button>'

# 2. دکمه حذف کنار ذخیره در template
OLD2 = "onclick=\"saveProduct('${p.id}', this)\">💾 ذخیره</button>"
NEW2 = "onclick=\"saveProduct('${p.id}', this)\">💾 ذخیره</button><button class=\"btn btn-danger btn-sm\" style=\"margin-right:4px\" onclick=\"deleteProd('${p.id}',this)\">🗑 حذف</button>"

if OLD1 in html:
    html = html.replace(OLD1, NEW1)
    print('OK: New Product button added')
else:
    print('WARN: reload button not found - check manually')

if OLD2 in html:
    html = html.replace(OLD2, NEW2)
    print('OK: Delete button added to rows')
else:
    print('WARN: save button template not found')

hp.write_text(html, encoding='utf-8')
print('DONE')