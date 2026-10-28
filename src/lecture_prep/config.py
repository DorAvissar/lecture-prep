"""Application settings, loaded from environment variables (and a local .env file).

Secrets never live in code: every key the app needs is declared here and
documented in .env.example.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = "postgresql+psycopg://lecture_prep:lecture_prep@localhost:5432/lecture_prep"

    # OneDrive via Microsoft Graph. The client ID comes from an Azure app registration (no secret needed:
    # it is a "public client" that signs in with the device-code flow).
    ms_client_id: str | None = None
    ms_token_cache_path: Path = Path(".cache/msal_token_cache.json")


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance so the environment is read only once."""
    return Settings()
