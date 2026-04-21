from contextlib import contextmanager
import psycopg
from clincore.core.config import settings


@contextmanager
def session_scope():
    url = (
        settings.DATABASE_URL
        .replace("postgresql+asyncpg://", "postgresql://")
        .replace("postgresql+psycopg://", "postgresql://")
        .replace("postgresql+psycopg_async://", "postgresql://")
    )
    conn = psycopg.connect(url)
    try:
        yield conn
    finally:
        conn.close()
