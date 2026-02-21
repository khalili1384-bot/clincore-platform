from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = "ClinCore Platform"
    ENV: str = "development"
    DEBUG: bool = True

    DATABASE_URL: str = "postgresql+psycopg://clincore_user:password@localhost:5432/clincore"

    JWT_SECRET: str = "change_this_in_production"
    JWT_ALGORITHM: str = "HS256"

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
