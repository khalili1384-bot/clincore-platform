import pathlib, re
hp = pathlib.Path(r'D:\clincore-platform\src\clincore\templates\explorer.html')
html = hp.read_text(encoding='utf-8')
m = re.search(r'(function saveProduct[\s\S]{0,800}?\n\})', html)
if m: print("=SAVE=\n", m.group(1))
m3 = re.search(r'(async function \w*[Pp]roduct\w*[\s\S]{0,800}?\n\s*\})', html)
if m3: print("=LOAD=\n", m3.group(1))
m4 = re.search(r'(`[\s\S]{0,1200}p\.id[\s\S]{0,600}?`)', html)
if m4: print("=ROW=\n", m4.group(0)[:900])