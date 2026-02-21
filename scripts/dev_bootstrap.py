# scripts/dev_bootstrap.py
# Run: python scripts/dev_bootstrap.py

import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)

CHECKS = []

def check(name, requires_db=False):
    def decorator(fn):
        CHECKS.append((name, fn, requires_db))
        return fn
    return decorator

# --- Layer 1: Environment (no clincore import) ---

@check("Python >= 3.11")
def _():
    assert sys.version_info >= (3, 11), f"Python {sys.version} — need 3.11+"

@check(".env exists")
def _():
    assert (ROOT / ".env").exists(), f".env not found in {ROOT}"

@check(".env has no BOM")
def _():
    raw = (ROOT / ".env").read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "BOM detected in .env (must be UTF-8 without BOM)"

@check(".env contains DATABASE_URL")
def _():
    content = (ROOT / ".env").read_text(encoding="utf-8")
    assert "DATABASE_URL=" in content, "DATABASE_URL missing in .env"

@check("DATABASE_URL uses 127.0.0.1 (not localhost)")
def _():
    content = (ROOT / ".env").read_text(encoding="utf-8")
    line = next((l for l in content.splitlines() if l.startswith("DATABASE_URL=")), "")
    assert line, "DATABASE_URL line not found"
    assert "localhost" not in line, f"localhost found in DATABASE_URL: {line}"

@check("alembic.ini exists")
def _():
    assert (ROOT / "alembic.ini").exists(), "alembic.ini not found"

@check("alembic.ini has no BOM")
def _():
    raw = (ROOT / "alembic.ini").read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "BOM detected in alembic.ini"

@check("clincore package importable")
def _():
    import importlib.util
    spec = importlib.util.find_spec("clincore")
    assert spec is not None, "clincore not importable. Fix packaging (pip install -e .) or PYTHONPATH."

# --- Layer 2: DB checks (only if env layer passes) ---

@check("DB: basic connect (SELECT 1)", requires_db=True)
def _():
    import asyncio
    from sqlalchemy import text
    from clincore.db import engine

    async def ping():
        async with engine.connect() as conn:
            r = await conn.execute(text("SELECT 1"))
            assert r.scalar() == 1

    asyncio.run(ping())

@check("DB: required tables exist", requires_db=True)
def _():
    import asyncio
    from sqlalchemy import text
    from clincore.db import engine

    REQUIRED = {"alembic_version", "tenants", "users", "patients", "cases"}

    async def tables():
        async with engine.connect() as conn:
            r = await conn.execute(text("""
                SELECT tablename FROM pg_tables WHERE schemaname='public'
            """))
            existing = {row[0] for row in r.fetchall()}
            missing = REQUIRED - existing
            assert not missing, f"Missing tables: {missing} (run: alembic upgrade head)"

    asyncio.run(tables())

def main():
    print("\n" + "="*52)
    print("  🔍 ClinCore Dev Bootstrap")
    print(f"  Root: {ROOT}")
    print("="*52 + "\n")

    env_ok = True
    passed = 0
    failed = 0

    for name, fn, requires_db in CHECKS:
        if requires_db and not env_ok:
            print(f"  ⏭  {name}  [skip — env not OK]")
            continue
        try:
            fn()
            print(f"  ✅ {name}")
            passed += 1
        except Exception as e:
            print(f"  ❌ {name}")
            print(f"     ↳ {e}")
            failed += 1
            if not requires_db:
                env_ok = False

    print("\n" + "="*52)
    print(f"  Result: {passed} green / {failed} red")
    print("="*52 + "\n")

    sys.exit(1 if failed else 0)

if __name__ == "__main__":
    main()