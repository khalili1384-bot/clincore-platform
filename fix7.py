import pathlib, re
hp = pathlib.Path(r'D:\clincore-platform\src\clincore\templates\shop\index.html')
html = hp.read_text(encoding='utf-8')

OLD = 'return `<div class="card">'
NEW = 'return `<div class="card" onclick="openProdDetail(\'${p.id}\')" style="cursor:pointer">'

if 'onclick="openProdDetail' not in html:
    if OLD in html:
        html = html.replace(OLD, NEW)
        hp.write_text(html, encoding='utf-8')
        print('OK: card is now clickable')
    else:
        print('WARN: card pattern not found')
        m = re.search(r'return `<div[^>]{0,100}card', html)
        if m: print('Found:', html[m.start():m.start()+80])
else:
    print('SKIP: already patched')