# ClinCore Platform (Phase 1 Lite)

FastAPI + PostgreSQL (RLS multi-tenant, fail-closed) + Alembic + pytest.

## Quick start (Docker)

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec api alembic upgrade head
docker compose exec api pytest -q
```

Open: http://localhost:8000/docs

## Local (Linux/macOS)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e ".[dev]"

cp .env.example .env
export $(cat .env | xargs)  # or set vars manually

alembic upgrade head
pytest -q
uvicorn app.main:app --reload
```

## Local (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e ".[dev]"

Copy-Item .env.example .env
# then set env vars in your session:
Get-Content .env | ForEach-Object {
  if ($_ -match '^(?<k>[^#=]+)=(?<v>.+)$') { [Environment]::SetEnvironmentVariable($matches.k, $matches.v) }
}

alembic upgrade head
pytest -q
uvicorn app.main:app --reload
```

## Tenant context usage (required)

All business DB access must run via `in_tenant_tx(...)`.
See `app/core/db/tenant.py` and tests under `tests/test_rls_fail_closed.py`.

Example call:
- Header: `X-Tenant-Id: <tenant_uuid>`
- POST `/patients`
- GET `/patients`
