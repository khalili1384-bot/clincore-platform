from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    DATABASE_URL: str
    REPERTORY_DB_PATH: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "ClinCore Platform"
    ENV: str = "development"
    DEBUG: bool = True

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if "localhost" in v:
            raise ValueError(
                "DATABASE_URL must use 127.0.0.1 instead of localhost."
            )

        if "psycopg_async" not in v:
            raise ValueError(
                "Async engine requires 'postgresql+psycopg_async://' URL."
            )

        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()