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

    # Google (Calendar + Drive). The client file is downloaded from Google Cloud Console; the token file is
    # written by `uv run python -m lecture_prep.google_api.login`. Both folders are git-ignored.
    google_client_secret_path: Path = Path(".secrets/google_client_secret.json")
    google_token_path: Path = Path(".cache/google_token.json")
    # The Drive folder that holds one sub-folder per course, e.g. "Lectures".
    drive_lectures_folder: str = "Lectures"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance so the environment is read only once."""
    return Settings()
