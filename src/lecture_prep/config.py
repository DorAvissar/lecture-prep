"""Application settings, loaded from environment variables (and a local .env file).

Secrets never live in code: every key the app needs is declared here and
documented in .env.example.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = "postgresql+psycopg://lecture_prep:lecture_prep@localhost:5432/lecture_prep"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance so the environment is read only once."""
    return Settings()
