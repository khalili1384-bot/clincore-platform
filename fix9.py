import pathlib
hp = pathlib.Path(r'D:\clincore-platform\src\clincore\templates\shop\index.html')
html = hp.read_text(encoding='utf-8')

OLD = 'window.openProdDetail = function(id) {\n    const p = (window.products||window.allProds||[]).find(x=>x.id===id);'
NEW = 'window.openProdDetail = function(id) {\n    const p = (window.allProducts||window.products||window.allProds||[]).find(x=>String(x.id)===String(id));'

if 'window.allProducts||' not in html:
    if 'window.products||window.allProds||' in html:
        html = html.replace(
            'window.products||window.allProds||',
            'window.allProducts||window.products||window.allProds||'
        )
        # همچنین fix مقایسه id
        html = html.replace(
            '.find(x=>x.id===id)',
            '.find(x=>String(x.id)===String(id))'
        )
        hp.write_text(html, encoding='utf-8')
        print('OK: patched — Ctrl+Shift+R')
    else:
        print('WARN: pattern not found — dump:')
        idx = html.find('openProdDetail = function')
        if idx >= 0: print(repr(html[idx:idx+200]))
else:
    print('SKIP: already patched')