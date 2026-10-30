"""Write the cloud's environment variables to cloud.env (git-ignored), ready to paste into the host:

    uv run python -m lecture_prep.cloud_env "<database URL from Neon>"

Values come from your .env and your Google token file; TICK_SECRET is generated fresh, so the outside
scheduler must send the same value. The file holds secrets - paste it, then delete it.
"""

import json
import secrets
import sys
from pathlib import Path

from lecture_prep.config import Settings, get_settings, normalize_database_url

OUTPUT = Path("cloud.env")


def cloud_variables(
    settings: Settings, google_token: str, database_url: str, tick_secret: str
) -> dict[str, str]:
    def secret(value) -> str:
        return value.get_secret_value() if value is not None else ""

    return {
        "ENVIRONMENT": "production",
        "DATABASE_URL": database_url,
        "TICK_SECRET": tick_secret,
        "TIMEZONE": settings.timezone,
        "CALENDAR_IDS": json.dumps(settings.calendar_ids, ensure_ascii=False),
        "DRIVE_LECTURES_FOLDER": settings.drive_lectures_folder,
        "GOOGLE_TOKEN_JSON": json.dumps(json.loads(google_token), separators=(",", ":")),
        "LLM_PROVIDER": settings.llm_provider,
        "LLM_FALLBACK_PROVIDER": settings.llm_fallback_provider or "",
        "LLM_FALLBACK_MODEL": settings.llm_fallback_model or "",
        "GEMINI_API_KEY": secret(settings.gemini_api_key),
        "GEMINI_MODEL": settings.gemini_model,
        "ANTHROPIC_API_KEY": secret(settings.anthropic_api_key),
        "ANTHROPIC_MODEL": settings.anthropic_model,
        "TELEGRAM_BOT_TOKEN": secret(settings.telegram_bot_token),
        "TELEGRAM_CHAT_ID": str(settings.telegram_chat_id or ""),
        "MORNING_HOUR": str(settings.morning_hour),
        "REMINDER_MINUTES": str(settings.reminder_minutes),
    }


def clean_database_url(raw: str) -> str:
    """Forgive copy-paste noise (spaces, quotes, <angle brackets>) and a missing postgresql:// prefix."""
    url = normalize_database_url(raw)
    if url and "@" not in url:
        raise SystemExit(
            "That does not look like a database URL: expected postgresql://user:password@host/db"
        )
    return url


def main() -> None:
    settings = get_settings()
    database_url = clean_database_url(sys.argv[1] if len(sys.argv) > 1 else "")
    google_token = settings.google_token_path.read_text(encoding="utf-8")
    variables = cloud_variables(settings, google_token, database_url, secrets.token_urlsafe(32))
    OUTPUT.write_text("".join(f"{name}={value}\n" for name, value in variables.items()), encoding="utf-8")
    print(f"Wrote {len(variables)} variables to {OUTPUT.resolve()}")
    print("It contains secrets: paste it into the host, put TICK_SECRET in the scheduler, then delete it.")
    missing = [name for name, value in variables.items() if not value]
    if missing:
        print("Empty, fill in before deploying:", ", ".join(missing))


if __name__ == "__main__":
    main()
