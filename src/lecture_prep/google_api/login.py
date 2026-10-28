"""One-time Google sign-in: uv run python -m lecture_prep.google_api.login

Opens the browser for Google's consent screen, caches the token, then lists the course folders inside
DRIVE_LECTURES_FOLDER to prove that Drive access works.
"""

import sys

from lecture_prep.config import get_settings
from lecture_prep.google_api.auth import GoogleAuthError, login_interactive
from lecture_prep.google_api.drive import DriveClient, FolderNotFoundError


def main() -> None:
    settings = get_settings()
    try:
        login_interactive(settings.google_client_secret_path, settings.google_token_path)
    except GoogleAuthError as error:
        sys.exit(str(error))
    print(f"Signed in. Token saved to {settings.google_token_path}")

    with DriveClient.from_settings(settings) as drive:
        try:
            courses = [
                item.name for item in drive.list_folder(settings.drive_lectures_folder) if item.is_folder
            ]
        except FolderNotFoundError:
            sys.exit(
                f"Drive folder '{settings.drive_lectures_folder}' was not found - create it in Google Drive."
            )
    print(f"Course folders in '{settings.drive_lectures_folder}':", ", ".join(courses) or "(none yet)")


if __name__ == "__main__":
    main()
