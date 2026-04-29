import pathlib, re
hp = pathlib.Path(r'D:\clincore-platform\src\clincore\templates\shop\index.html')
html = hp.read_text(encoding='utf-8')
m = re.search(r'return `<div class="card">([\s\S]{0,1500}?)`;', html)
if m: print("=FULL CARD=\n", m.group(0))