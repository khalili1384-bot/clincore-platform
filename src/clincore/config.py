from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "ClinCore Platform"
    ENV: str = "development"
    DEBUG: bool = True

    # ❗ No default → Fail fast if missing
    DATABASE_URL: str


@lru_cache
def get_settings() -> Settings:
    return Settings()


# 👇 این را اضافه کن
settings = get_settings()