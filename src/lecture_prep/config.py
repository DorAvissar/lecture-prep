"""Application settings, loaded from environment variables (and a local .env file).

Secrets never live in code: every key the app needs is declared here and
documented in .env.example.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # env_ignore_empty: a key left blank in .env (TELEGRAM_CHAT_ID=) means "not set", not an empty value.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)

    environment: str = "development"
    database_url: str = "postgresql+psycopg://lecture_prep:lecture_prep@localhost:5432/lecture_prep"
    # Your local time zone: "today" and lecture times are computed in it (IANA name).
    timezone: str = "Asia/Jerusalem"

    # Google (Calendar + Drive). The client file is downloaded from Google Cloud Console; the token file is
    # written by `uv run python -m lecture_prep.google_api.login`. Both folders are git-ignored.
    google_client_secret_path: Path = Path(".secrets/google_client_secret.json")
    google_token_path: Path = Path(".cache/google_token.json")
    # Calendars to read lectures from: "primary" is your own; add the id of a calendar shared with you.
    calendar_ids: list[str] = ["primary"]
    # The Drive folder that holds one sub-folder per course, e.g. "Lectures".
    drive_lectures_folder: str = "Lectures"
    # Which model writes summaries and answers questions: "claude" or "gemini".
    llm_provider: Literal["claude", "gemini"] = "claude"
    anthropic_api_key: SecretStr | None = None  # None: the SDK falls back to its own credential lookup
    anthropic_model: str = "claude-opus-5-5"
    gemini_api_key: SecretStr | None = None  # from https://aistudio.google.com
    gemini_model: str = "gemini-pro-latest"

    # Telegram. The token comes from @BotFather; find the chat id with
    # `uv run python -m lecture_prep.telegram.chat_id` after sending your bot any message.
    telegram_bot_token: SecretStr | None = None
    telegram_chat_id: int | None = None
    morning_hour: int = 7  # local hour of the morning message
    reminder_minutes: int = 30  # how long before a lecture its reminder is sent
    # The app's public https address, e.g. https://lecture-prep.up.railway.app. Telegram buttons open the
    # Mini App there; until it is set, messages go without buttons.
    public_url: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance so the environment is read only once."""
    return Settings()
