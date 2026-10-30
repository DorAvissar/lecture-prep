"""Google OAuth sign-in shared by Calendar and Drive: one consent screen, one cached token file.

Sign in once with `uv run python -m lecture_prep.google_api.login`. The saved refresh token lets the app
get fresh access tokens (they expire after an hour) without a browser.

In the cloud there is no token file: the same JSON goes in the GOOGLE_TOKEN_JSON variable, and fresh
access tokens are kept in memory only (the refresh token itself never changes).
"""

import json
from collections.abc import Callable, Generator
from pathlib import Path

import httpx
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Read-only access: the app never changes your calendar or files.
SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]
LOGIN_HINT = "Run: uv run python -m lecture_prep.google_api.login"


class GoogleAuthError(RuntimeError):
    """Raised when there is no usable Google sign-in; the message says how to fix it."""


def login_interactive(client_secret_path: Path, token_path: Path) -> Credentials:
    """Open the browser for Google's consent screen, then save the resulting token."""
    if not client_secret_path.exists():
        raise GoogleAuthError(
            f"Missing {client_secret_path}. Download the OAuth client file from Google Cloud Console "
            "(see 'Connecting Google' in the README)."
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), SCOPES)
    credentials = flow.run_local_server(port=0)  # temporary local page that receives Google's answer
    save_credentials(credentials, token_path)
    return credentials


def load_credentials(token_path: Path) -> Credentials:
    """Return valid credentials from the token file, refreshing and re-saving them when expired."""
    if not token_path.exists():
        raise GoogleAuthError(f"Not signed in to Google. {LOGIN_HINT}")
    credentials = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if credentials.valid:
        return credentials
    if not credentials.refresh_token:
        raise GoogleAuthError(f"Google sign-in has no refresh token. {LOGIN_HINT}")
    try:
        credentials.refresh(Request())
    except RefreshError as error:
        raise GoogleAuthError(f"Google sign-in expired or was revoked ({error}). {LOGIN_HINT}") from error
    save_credentials(credentials, token_path)
    return credentials


def credentials_from_json(token_json: str) -> Credentials:
    """Valid credentials from the token file's JSON content, refreshed in memory."""
    try:
        credentials = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
    except (ValueError, KeyError) as error:
        raise GoogleAuthError(f"GOOGLE_TOKEN_JSON is not a valid token ({error}).") from error
    try:
        credentials.refresh(Request())
    except RefreshError as error:
        raise GoogleAuthError(f"Google sign-in expired or was revoked ({error}). {LOGIN_HINT}") from error
    return credentials


def save_credentials(credentials: Credentials, token_path: Path) -> None:
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(credentials.to_json(), encoding="utf-8")


class TokenSource:
    """Callable that returns a current access token, reloading/refreshing only when needed.

    Reads the token file, or - when `token_json` is given (the cloud) - that JSON instead.
    """

    def __init__(self, token_path: Path, token_json: str | None = None) -> None:
        self._token_path = token_path
        self._token_json = token_json
        self._credentials: Credentials | None = None

    def __call__(self) -> str:
        if self._credentials is None or not self._credentials.valid:
            if self._token_json is not None:
                self._credentials = credentials_from_json(self._token_json)
            else:
                self._credentials = load_credentials(self._token_path)
        return self._credentials.token


class BearerAuth(httpx.Auth):
    """Adds `Authorization: Bearer <token>` to every request made by an httpx client."""

    def __init__(self, get_token: Callable[[], str]) -> None:
        self._get_token = get_token

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        request.headers["Authorization"] = f"Bearer {self._get_token()}"
        yield request
