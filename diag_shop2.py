import pathlib, re
hp = pathlib.Path(r'D:\clincore-platform\src\clincore\templates\shop\index.html')
html = hp.read_text(encoding='utf-8')
m = re.search(r'return `<div class="card">([\s\S]{0,800})`', html)
if m: print("=CARD=\n", m.group(0)[:900])
m2 = re.search(r'(function.*?openModal|function.*?showModal|\.open[\s\S]{0,600}modal[\s\S]{0,400})', html, re.I)
if m2: print("=MODAL_FUNC=\n", m2.group(0)[:600])
m3 = re.search(r'(<div class="modal[\s\S]{0,800})</div>', html)
if m3: print("=MODAL_HTML=\n", m3.group(0)[:600])