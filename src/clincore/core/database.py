from contextlib import contextmanager
import psycopg
from clincore.core.config import settings


@contextmanager
def session_scope():
    conn = psycopg.connect(settings.DATABASE_URL.replace("+psycopg_async", ""))
    try:
        yield conn
    finally:
        conn.close()
