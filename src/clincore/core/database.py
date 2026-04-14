"""
Database connection utilities.
"""
import os
from contextlib import contextmanager
import psycopg

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    _host = os.getenv("DB_HOST", "127.0.0.1")
    _port = os.getenv("DB_PORT", "5432")
    _user = os.getenv("DB_USER", "clincore_user")
    _pass = os.getenv("DB_PASSWORD", "")
    _name = os.getenv("DB_NAME", "clincore")
    DATABASE_URL = f"postgresql://{_user}:{_pass}@{_host}:{_port}/{_name}"


@contextmanager
def session_scope():
    """Context manager for database connection."""
    conn = psycopg.connect(DATABASE_URL)
    try:
        yield conn
    finally:
        conn.close()
