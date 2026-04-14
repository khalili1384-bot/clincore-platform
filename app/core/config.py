import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg_async://clincore_user:805283631@127.0.0.1:5432/clincore",
    )


settings = Settings()
