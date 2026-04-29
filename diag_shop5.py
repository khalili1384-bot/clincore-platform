import pathlib, re
hp = pathlib.Path(r'D:\clincore-platform\src\clincore\templates\shop\index.html')
html = hp.read_text(encoding='utf-8')
m = re.search(r'return `<div class="card">([\s\S]{0,600}?)`\s*;', html)
if m: print("CARD:\n", m.group(0)[:700])