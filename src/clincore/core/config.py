import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg_async://clincore_user:805283631@127.0.0.1:5432/clincore",
    )
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-min-32-chars-long-for-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60


settings = Settings()
