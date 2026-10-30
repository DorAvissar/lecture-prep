"""Application settings, loaded from environment variables (and a local .env file).

Secrets never live in code: every key the app needs is declared here and
documented in .env.example.
"""

import re
from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LOCAL_DATABASE_URL = "postgresql+psycopg://lecture_prep:lecture_prep@localhost:5432/lecture_prep"
POSTGRES_SCHEME = re.compile(r"^postgres(?:ql)?(?:\+\w+)?://")


def normalize_database_url(raw: str) -> str:
    """A database URL as SQLAlchemy needs it, forgiving what copy-pasting into a host's settings adds.

    Removes spaces, quotes and <angle brackets>, a pasted "DATABASE_URL=" or "psql" in front, adds a
    missing postgresql:// and names the psycopg driver (hosts hand out plain postgresql:// URLs).
    """
    url = raw.strip()
    url = re.sub(r"^(DATABASE_URL\s*=|psql\s+)", "", url).strip()
    url = url.strip("<>\"'` ").strip()
    if not url:
        return url
    if not POSTGRES_SCHEME.match(url):
        url = "postgresql://" + url
    return re.sub(r"^postgres(?:ql)?://", "postgresql+psycopg://", url)


class Settings(BaseSettings):
    # env_ignore_empty: a key left blank in .env (TELEGRAM_CHAT_ID=) means "not set", not an empty value.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)

    environment: str = "development"
    database_url: str = LOCAL_DATABASE_URL
    # Your local time zone: "today" and lecture times are computed in it (IANA name).
    timezone: str = "Asia/Jerusalem"

    # Google (Calendar + Drive). The client file is downloaded from Google Cloud Console; the token file is
    # written by `uv run python -m lecture_prep.google_api.login`. Both folders are git-ignored.
    google_client_secret_path: Path = Path(".secrets/google_client_secret.json")
    google_token_path: Path = Path(".cache/google_token.json")
    # In the cloud, the token file's content instead of the file itself.
    google_token_json: SecretStr | None = None
    # Calendars to read lectures from: "primary" is your own; add the id of a calendar shared with you.
    calendar_ids: list[str] = ["primary"]
    # The Drive folder that holds one sub-folder per course, e.g. "Lectures".
    drive_lectures_folder: str = "Lectures"
    # Which model writes summaries and answers questions: "claude" or "gemini". Gemini Pro won a blind
    # comparison on a real lecture; Claude Sonnet (second place) answers whenever Gemini fails.
    llm_provider: Literal["claude", "gemini"] = "gemini"
    llm_fallback_provider: Literal["claude", "gemini"] | None = "claude"  # None: no backup
    llm_fallback_model: str | None = "claude-sonnet-5-5"
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
    # Render sets RENDER_EXTERNAL_URL on its own, so there it needs no setting.
    public_url: str | None = Field(
        default=None, validation_alias=AliasChoices("PUBLIC_URL", "RENDER_EXTERNAL_URL")
    )
    # Password for POST /internal/tick, the address an outside scheduler calls to run a tick.
    tick_secret: SecretStr | None = None

    @field_validator("database_url")
    @classmethod
    def clean_database_url(cls, url: str) -> str:
        return normalize_database_url(url)

    @model_validator(mode="after")
    def production_needs_a_real_database(self) -> Self:
        if self.environment == "production" and self.database_url == LOCAL_DATABASE_URL:
            raise ValueError("DATABASE_URL is not set - in production it must point to the cloud database")
        return self

    @property
    def google_token_json_value(self) -> str | None:
        return self.google_token_json.get_secret_value() if self.google_token_json else None


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance so the environment is read only once."""
    return Settings()
