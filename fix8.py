import pathlib
hp = pathlib.Path(r'D:\clincore-platform\src\clincore\templates\shop\index.html')
html = hp.read_text(encoding='utf-8')

OLD = '<div class="modal-overlay" id="prodDetailModal"'
NEW = '<div id="prodDetailModal"'

if OLD in html:
    html = html.replace(OLD, NEW)
    hp.write_text(html, encoding='utf-8')
    print('OK: class removed, Ctrl+Shift+R')
else:
    print('ALREADY fixed or not found')