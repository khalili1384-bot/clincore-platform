import pathlib, re
hp = pathlib.Path(r'D:\clincore-platform\explorer.html')
html = hp.read_text(encoding='utf-8')
print('SIZE:', len(html))
print('HAS_PATCH:', 'modal-new-prod' in html)
for b in re.findall(r'<button[^>]{0,150}>[^<]{0,40}</button>', html)[:15]:
    print('BTN:', b[:120])
for i in re.findall(r'id="([^"]{1,40})"', html)[:30]:
    print('ID:', i)