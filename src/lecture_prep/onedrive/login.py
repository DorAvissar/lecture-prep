"""One-time OneDrive sign-in: uv run python -m lecture_prep.onedrive.login

Prints a short code to enter at microsoft.com/devicelogin, caches the resulting token, then lists the
drive's top-level folders to prove the connection works.
"""

import sys

from lecture_prep.config import get_settings
from lecture_prep.onedrive.auth import OneDriveAuthError, TokenProvider
from lecture_prep.onedrive.client import OneDriveClient


def main() -> None:
    settings = get_settings()
    if not settings.ms_client_id:
        sys.exit("MS_CLIENT_ID is not set. Add your Azure app's client ID to .env first.")
    try:
        TokenProvider(settings.ms_client_id, settings.ms_token_cache_path).login_interactive()
        with OneDriveClient.from_settings(settings) as client:
            folders = [item.name for item in client.list_folder("/") if item.is_folder]
    except OneDriveAuthError as error:
        sys.exit(str(error))
    print(f"Signed in. Token cached at {settings.ms_token_cache_path}")
    print("Top-level folders:", ", ".join(folders) or "(none)")


if __name__ == "__main__":
    main()
