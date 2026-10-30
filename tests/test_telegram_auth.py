import json
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import pytest

from lecture_prep.web.telegram_auth import InvalidInitData, signature, verify_init_data

TOKEN = "123:secret"
NOW = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)


def init_data(user_id: int = 42, signed_at: datetime = NOW, token: str = TOKEN, **extra: str) -> str:
    fields = {
        "auth_date": str(int(signed_at.timestamp())),
        "user": json.dumps({"id": user_id, "first_name": "דור"}),
        "query_id": "AAE",
        **extra,
    }
    return urlencode({**fields, "hash": signature(fields, token)})


def test_valid_init_data_returns_the_user_id():
    assert verify_init_data(init_data(), TOKEN, NOW) == 42


def test_data_signed_with_another_token_is_rejected():
    with pytest.raises(InvalidInitData):
        verify_init_data(init_data(token="999:other"), TOKEN, NOW)


def test_tampered_data_is_rejected():
    tampered = init_data().replace("%22id%22%3A+42", "%22id%22%3A+43")

    with pytest.raises(InvalidInitData):
        verify_init_data(tampered, TOKEN, NOW)


def test_old_data_is_rejected():
    with pytest.raises(InvalidInitData, match="expired"):
        verify_init_data(init_data(signed_at=NOW - timedelta(days=2)), TOKEN, NOW)


def test_missing_hash_is_rejected():
    with pytest.raises(InvalidInitData):
        verify_init_data("auth_date=1&user=%7B%7D", TOKEN, NOW)
