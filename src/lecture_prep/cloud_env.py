"""Write the cloud's environment variables to railway.env (git-ignored), ready to paste into Railway:

    uv run python -m lecture_prep.cloud_env

Values come from your .env and your Google token file. Database and public address are Railway
reference variables, filled in by Railway itself: the Postgres service must be named "Postgres" and the
web service "web". The file holds secrets - paste it, then delete it.
"""

import json
from pathlib import Path

from lecture_prep.config import Settings, get_settings

OUTPUT = Path("railway.env")


def cloud_variables(settings: Settings, google_token: str) -> dict[str, str]:
    def secret(value) -> str:
        return value.get_secret_value() if value is not None else ""

    return {
        "ENVIRONMENT": "production",
        "DATABASE_URL": "${{Postgres.DATABASE_URL}}",
        "PUBLIC_URL": "https://${{web.RAILWAY_PUBLIC_DOMAIN}}",
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


def main() -> None:
    settings = get_settings()
    google_token = settings.google_token_path.read_text(encoding="utf-8")
    variables = cloud_variables(settings, google_token)
    missing = [name for name, value in variables.items() if not value]
    OUTPUT.write_text("".join(f"{name}={value}\n" for name, value in variables.items()), encoding="utf-8")
    print(
        f"Wrote {len(variables)} variables to {OUTPUT.resolve()} (contains secrets - delete after pasting)."
    )
    if missing:
        print("Empty, fill in before deploying:", ", ".join(missing))


if __name__ == "__main__":
    main()
