from pathlib import Path


def test_no_raw_engine_creation_outside_core_shared_db() -> None:
    repo = Path(__file__).resolve().parents[1]

    allowed = {
        repo / "app" / "core" / "shared" / "db.py",
        repo / "src" / "clincore" / "db.py",
        repo / "alembic" / "env.py",
        repo / "tests" / "conftest.py",
        Path(__file__).resolve(),  # ignore this file itself
    }

    offenders: list[str] = []

    for p in repo.rglob("*.py"):
        if "venv" in str(p) or ".venv" in str(p) or "__pycache__" in str(p):
            continue

        if p in allowed:
            continue

        txt = p.read_text(encoding="utf-8")

        if "create_async_engine(" in txt or "create_engine(" in txt:
            offenders.append(str(p.relative_to(repo)))

    assert offenders == [], (
        "DB engine creation forbidden outside wrapper infra: "
        f"{offenders}"
    )
