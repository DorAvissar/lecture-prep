"""List and download Google Drive files through the Drive REST API (v3).

Drive has no "open this path" call - every file and folder is known by an ID. So a path like
"Lectures/Linear Algebra" is resolved one folder at a time, starting from the drive's root.
"""

from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Any, Self

import httpx

from lecture_prep.config import Settings
from lecture_prep.google_api.auth import BearerAuth, TokenSource

DRIVE_URL = "https://www.googleapis.com/drive/v3"
FOLDER_MIME = "application/vnd.google-apps.folder"
GOOGLE_APPS_MIME_PREFIX = "application/vnd.google-apps."  # Docs, Slides, Sheets: no raw bytes to download
FILE_FIELDS = "nextPageToken, files(id, name, mimeType, size, modifiedTime)"


class FolderNotFoundError(LookupError):
    """The requested Drive folder does not exist."""


@dataclass(frozen=True)
class DriveItem:
    id: str
    name: str
    path: str  # full path from the drive root, e.g. "/Lectures/Linear Algebra/lecture3.pdf"
    mime_type: str
    size: int
    modified_at: datetime

    @property
    def is_folder(self) -> bool:
        return self.mime_type == FOLDER_MIME

    @property
    def is_google_doc(self) -> bool:
        """Native Google Docs/Slides/Sheets, which must be exported (we export them as PDF)."""
        return self.mime_type.startswith(GOOGLE_APPS_MIME_PREFIX) and not self.is_folder


class DriveClient:
    """Thin wrapper over the Drive API. Takes an httpx.Client so tests can plug in a fake transport."""

    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    @classmethod
    def from_settings(cls, settings: Settings) -> Self:
        http = httpx.Client(
            base_url=DRIVE_URL,
            auth=BearerAuth(TokenSource(settings.google_token_path, settings.google_token_json_value)),
            follow_redirects=True,
            timeout=30,
        )
        return cls(http)

    def list_folder(self, path: str) -> list[DriveItem]:
        """Return the files and sub-folders directly inside `path` ("" or "/" is My Drive's root)."""
        folder_id = self._resolve_folder(path)
        prefix = "/" + path.strip("/") if path.strip("/") else ""
        return [
            _to_item(raw, prefix) for raw in self._search(f"'{folder_id}' in parents and trashed = false")
        ]

    def download(self, item: DriveItem) -> bytes:
        """Return a file's bytes. Native Google documents are exported to PDF."""
        if item.is_google_doc:
            response = self._http.get(f"/files/{item.id}/export", params={"mimeType": "application/pdf"})
        else:
            response = self._http.get(f"/files/{item.id}", params={"alt": "media"})
        response.raise_for_status()
        return response.content

    def _resolve_folder(self, path: str) -> str:
        folder_id = "root"
        for name in filter(None, path.split("/")):
            matches = self._search(
                f"'{folder_id}' in parents and name = '{_escape(name)}' "
                f"and mimeType = '{FOLDER_MIME}' and trashed = false"
            )
            if not matches:
                raise FolderNotFoundError(path)
            folder_id = matches[0]["id"]
        return folder_id

    def _search(self, query: str) -> list[dict[str, Any]]:
        """Run a Drive search, following nextPageToken until every page is read."""
        params = {"q": query, "fields": FILE_FIELDS, "pageSize": 1000, "orderBy": "name"}
        files: list[dict[str, Any]] = []
        while True:
            response = self._http.get("/files", params=params)
            response.raise_for_status()
            page = response.json()
            files.extend(page.get("files", []))
            if "nextPageToken" not in page:
                return files
            params["pageToken"] = page["nextPageToken"]

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        self.close()


def _escape(name: str) -> str:
    """Escape a name for a Drive query string, where values are wrapped in single quotes."""
    return name.replace("\\", "\\\\").replace("'", "\\'")


def _to_item(raw: dict[str, Any], prefix: str) -> DriveItem:
    return DriveItem(
        id=raw["id"],
        name=raw["name"],
        path=f"{prefix}/{raw['name']}",
        mime_type=raw["mimeType"],
        size=int(raw.get("size", 0)),  # Drive sends size as a string; native Google docs have none
        modified_at=datetime.fromisoformat(raw["modifiedTime"]),
    )
