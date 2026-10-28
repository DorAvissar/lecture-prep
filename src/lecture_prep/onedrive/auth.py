"""Microsoft sign-in with MSAL's device-code flow and a token cache on disk.

Sign in once with `uv run python -m lecture_prep.onedrive.login`; after that the cached refresh token
lets the app get fresh access tokens silently, with no browser involved.
"""

from collections.abc import Callable, Generator
from pathlib import Path

import httpx
import msal

# Read-only access to the signed-in user's files. MSAL adds offline_access (refresh tokens) by itself.
SCOPES = ["Files.Read"]
# "common" accepts both personal Microsoft accounts and work/school accounts.
AUTHORITY = "https://login.microsoftonline.com/common"


class OneDriveAuthError(RuntimeError):
    """Raised when there is no usable sign-in; the message says how to fix it."""


class TokenProvider:
    def __init__(self, client_id: str, cache_path: Path) -> None:
        self._cache_path = cache_path
        self._cache = msal.SerializableTokenCache()
        if cache_path.exists():
            self._cache.deserialize(cache_path.read_text(encoding="utf-8"))
        self._app = msal.PublicClientApplication(client_id, authority=AUTHORITY, token_cache=self._cache)

    def get_token(self) -> str:
        """Return a valid access token, refreshing it silently. Never prompts the user."""
        accounts = self._app.get_accounts()
        result = self._app.acquire_token_silent(SCOPES, account=accounts[0]) if accounts else None
        if not result or "access_token" not in result:
            raise OneDriveAuthError(
                "Not signed in to OneDrive. Run: uv run python -m lecture_prep.onedrive.login"
            )
        self._save_cache()
        return result["access_token"]

    def login_interactive(self, show: Callable[[str], None] = print) -> None:
        """Device-code flow: show a short code, the user enters it at microsoft.com/devicelogin."""
        flow = self._app.initiate_device_flow(scopes=SCOPES)
        if "user_code" not in flow:
            raise OneDriveAuthError(f"Could not start sign-in: {flow.get('error_description', flow)}")
        show(flow["message"])
        result = self._app.acquire_token_by_device_flow(flow)  # blocks until the user finishes
        if "access_token" not in result:
            raise OneDriveAuthError(f"Sign-in failed: {result.get('error_description', result)}")
        self._save_cache()

    def _save_cache(self) -> None:
        if self._cache.has_state_changed:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(self._cache.serialize(), encoding="utf-8")


class BearerAuth(httpx.Auth):
    """Adds a fresh access token to every request.

    httpx drops the Authorization header when a redirect leaves the original host, so the token is not
    leaked to the pre-signed download URLs that Graph redirects file downloads to.
    """

    def __init__(self, get_token: Callable[[], str]) -> None:
        self._get_token = get_token

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        request.headers["Authorization"] = f"Bearer {self._get_token()}"
        yield request
