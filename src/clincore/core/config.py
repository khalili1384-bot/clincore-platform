import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str = "postgresql+psycopg_async://clincore_user:805283631@127.0.0.1:5432/clincore"
    SECRET_KEY: str = "dev-secret-key-min-32-chars-long-for-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    SUPER_ADMIN_KEY: str = ""


settings = Settings()
