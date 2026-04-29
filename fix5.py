import pathlib

hp = pathlib.Path(r'D:\clincore-platform\src\clincore\templates\explorer.html')
html = hp.read_text(encoding='utf-8')

OLD = 'allProducts = data.products || [];'
NEW = 'allProducts = data.products || []; window.allProducts = allProducts;'

if 'window.allProducts = allProducts' not in html:
    if OLD in html:
        html = html.replace(OLD, NEW)
        print('OK: window.allProducts exposed')
    else:
        print('WARN: pattern not found')
        import re
        m = re.search(r'allProducts\s*=\s*data\.products', html)
        if m: print('Found at:', m.start(), '|', html[m.start():m.start()+60])
else:
    print('SKIP: already patched')

hp.write_text(html, encoding='utf-8')
print('DONE - Ctrl+Shift+R')