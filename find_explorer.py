import pathlib, re
for f in pathlib.Path(r'D:\clincore-platform\src').rglob('*.py'):
    t = f.read_text(encoding='utf-8', errors='ignore')
    if 'explorer' in t.lower():
        print('FILE:', f)
        for line in t.splitlines():
            if 'explorer' in line.lower():
                print('  >', line.strip())