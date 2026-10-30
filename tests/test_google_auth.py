import json
from pathlib import Path

import pytest
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials

from lecture_prep.google_api.auth import GoogleAuthError, TokenSource, load_credentials, login_interactive


def write_token(path: Path, *, expiry: str) -> None:
    path.write_text(
        json.dumps(
            {
                "token": "access-123",
                "refresh_token": "refresh-456",
                "client_id": "client.apps.googleusercontent.com",
                "client_secret": "secret",
                "token_uri": "https://oauth2.googleapis.com/token",
                "expiry": expiry,
            }
        ),
        encoding="utf-8",
    )


def test_missing_token_file_says_how_to_sign_in(tmp_path: Path):
    with pytest.raises(GoogleAuthError, match="google_api.login"):
        load_credentials(tmp_path / "token.json")


def test_valid_token_is_used_without_refreshing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    token_path = tmp_path / "token.json"
    write_token(token_path, expiry="2099-01-01T00:00:00Z")
    monkeypatch.setattr(Credentials, "refresh", lambda self, request: pytest.fail("should not refresh"))

    assert TokenSource(token_path)() == "access-123"


def test_revoked_refresh_token_raises_a_clear_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    token_path = tmp_path / "token.json"
    write_token(token_path, expiry="2000-01-01T00:00:00Z")

    def refuse(self, request):
        raise RefreshError("invalid_grant")

    monkeypatch.setattr(Credentials, "refresh", refuse)

    with pytest.raises(GoogleAuthError, match="expired or was revoked"):
        load_credentials(token_path)


def test_login_without_client_file_points_to_the_readme(tmp_path: Path):
    with pytest.raises(GoogleAuthError, match="README"):
        login_interactive(tmp_path / "missing.json", tmp_path / "token.json")


TOKEN_INFO = {
    "token": "old",
    "refresh_token": "refresh-456",
    "client_id": "client.apps.googleusercontent.com",
    "client_secret": "secret",
    "token_uri": "https://oauth2.googleapis.com/token",
}


def test_token_json_from_the_environment_is_refreshed_in_memory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    def refresh(self, request):
        self.token = "fresh-789"

    monkeypatch.setattr(Credentials, "refresh", refresh)
    missing_file = tmp_path / "no-token-file.json"

    assert TokenSource(missing_file, json.dumps(TOKEN_INFO))() == "fresh-789"
    assert not missing_file.exists()  # nothing is written in the cloud


def test_broken_token_json_raises_a_clear_error(tmp_path: Path):
    with pytest.raises(GoogleAuthError, match="GOOGLE_TOKEN_JSON"):
        TokenSource(tmp_path / "x.json", "{not json")()
