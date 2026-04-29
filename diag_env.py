import pathlib
env = pathlib.Path(r'D:\clincore-platform\.env').read_text(encoding='utf-8')
for line in env.splitlines():
    line = line.strip()
    if line and not line.startswith('#'):
        k = line.split('=',1)[0].strip()
        print(k)