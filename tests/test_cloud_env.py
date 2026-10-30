import json

from lecture_prep.cloud_env import cloud_variables
from lecture_prep.config import Settings


def test_cloud_variables_carry_settings_secrets_and_railway_references():
    settings = Settings(
        _env_file=None,
        calendar_ids=["primary", "uni@post.bgu.ac.il"],
        gemini_api_key="g-key",
        telegram_bot_token="t-token",
        telegram_chat_id=42,
    )
    token = '{\n  "refresh_token": "r",\n  "client_id": "c"\n}'

    variables = cloud_variables(settings, token)

    assert variables["ENVIRONMENT"] == "production"
    assert variables["DATABASE_URL"] == "${{Postgres.DATABASE_URL}}"
    assert variables["PUBLIC_URL"] == "https://${{web.RAILWAY_PUBLIC_DOMAIN}}"
    assert json.loads(variables["CALENDAR_IDS"]) == ["primary", "uni@post.bgu.ac.il"]
    assert variables["GOOGLE_TOKEN_JSON"] == '{"refresh_token":"r","client_id":"c"}'  # one line
    assert variables["GEMINI_API_KEY"] == "g-key"
    assert variables["TELEGRAM_CHAT_ID"] == "42"
    assert all("\n" not in value for value in variables.values())
