import pathlib, re
for f in pathlib.Path(r'D:\clincore-platform').rglob('*.py'):
    t = f.read_text(encoding='utf-8', errors='ignore')
    if 'shop' in f.name.lower() and 'router' in t:
        for line in t.splitlines():
            if 'get(' in line and ('shop' in line.lower() or 'html' in line.lower()):
                print(f.name, '|', line.strip())
for f in pathlib.Path(r'D:\clincore-platform').rglob('*.html'):
    print('HTML:', f)