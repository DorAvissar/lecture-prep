from lecture_prep.config import Settings


def test_blank_values_count_as_not_set(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")

    settings = Settings(_env_file=None)

    assert settings.telegram_chat_id is None
    assert settings.anthropic_api_key is None
