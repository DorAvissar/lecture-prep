import json

from lecture_prep.cloud_env import cloud_variables
from lecture_prep.config import Settings


def test_cloud_variables_carry_settings_and_secrets():
    settings = Settings(
        _env_file=None,
        calendar_ids=["primary", "uni@post.bgu.ac.il"],
        gemini_api_key="g-key",
        telegram_bot_token="t-token",
        telegram_chat_id=42,
    )
    token = '{\n  "refresh_token": "r",\n  "client_id": "c"\n}'

    variables = cloud_variables(settings, token, "postgresql://neon/db?sslmode=require", "tick-123")

    assert variables["ENVIRONMENT"] == "production"
    assert variables["DATABASE_URL"] == "postgresql://neon/db?sslmode=require"
    assert variables["TICK_SECRET"] == "tick-123"
    assert "PUBLIC_URL" not in variables  # Render provides it
    assert json.loads(variables["CALENDAR_IDS"]) == ["primary", "uni@post.bgu.ac.il"]
    assert variables["GOOGLE_TOKEN_JSON"] == '{"refresh_token":"r","client_id":"c"}'  # one line
    assert variables["GEMINI_API_KEY"] == "g-key"
    assert variables["TELEGRAM_CHAT_ID"] == "42"
    assert all("\n" not in value for value in variables.values())


def test_database_url_survives_copy_paste_noise():
    from lecture_prep.cloud_env import clean_database_url

    assert clean_database_url(" <user:pw@ep-x.neon.tech/db?sslmode=require> ") == (
        "postgresql://user:pw@ep-x.neon.tech/db?sslmode=require"
    )
    assert clean_database_url("'postgresql://user:pw@h/db'") == "postgresql://user:pw@h/db"
