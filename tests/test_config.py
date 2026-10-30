from lecture_prep.config import Settings


def test_blank_values_count_as_not_set(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")

    settings = Settings(_env_file=None)

    assert settings.telegram_chat_id is None
    assert settings.anthropic_api_key is None


def test_hosted_database_urls_get_the_psycopg_driver():
    for given in ("postgresql://u:p@db:5432/x", "postgres://u:p@db:5432/x"):
        assert (
            Settings(_env_file=None, database_url=given).database_url == "postgresql+psycopg://u:p@db:5432/x"
        )


def test_explicit_driver_is_kept():
    url = "postgresql+psycopg://u:p@localhost:5432/x"

    assert Settings(_env_file=None, database_url=url).database_url == url
