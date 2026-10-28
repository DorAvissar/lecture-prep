"""List and download OneDrive files through the Microsoft Graph REST API."""

from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Any, Self
from urllib.parse import quote

import httpx

from lecture_prep.config import Settings
from lecture_prep.onedrive.auth import BearerAuth, OneDriveAuthError, TokenProvider

GRAPH_URL = "https://graph.microsoft.com/v1.0"


class FolderNotFoundError(LookupError):
    """The requested OneDrive folder does not exist."""


@dataclass(frozen=True)
class DriveItem:
    id: str
    name: str
    path: str  # full path from the drive root, e.g. "/Uni/Linear Algebra/lecture3.pdf"
    is_folder: bool
    size: int
    modified_at: datetime


class OneDriveClient:
    """Thin wrapper over Graph. Takes an httpx.Client so tests can plug in a fake transport."""

    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    @classmethod
    def from_settings(cls, settings: Settings) -> Self:
        if not settings.ms_client_id:
            raise OneDriveAuthError("MS_CLIENT_ID is not set. Add your Azure app's client ID to .env")
        tokens = TokenProvider(settings.ms_client_id, settings.ms_token_cache_path)
        http = httpx.Client(
            base_url=GRAPH_URL, auth=BearerAuth(tokens.get_token), follow_redirects=True, timeout=30
        )
        return cls(http)

    def list_folder(self, path: str) -> list[DriveItem]:
        """Return the files and sub-folders directly inside `path` ("" or "/" is the drive root)."""
        folder = path.strip("/")
        url: str | None = (
            f"/me/drive/root:/{quote(folder)}:/children" if folder else "/me/drive/root/children"
        )
        items: list[DriveItem] = []
        while url:  # Graph returns large folders in pages, linked by @odata.nextLink
            response = self._http.get(url)
            if response.status_code == httpx.codes.NOT_FOUND:
                raise FolderNotFoundError(path)
            response.raise_for_status()
            page = response.json()
            items.extend(_to_item(raw, folder) for raw in page["value"])
            url = page.get("@odata.nextLink")
        return items

    def download(self, item_id: str) -> bytes:
        """Return a file's content. Graph answers with a redirect to a short-lived download URL."""
        response = self._http.get(f"/me/drive/items/{item_id}/content")
        response.raise_for_status()
        return response.content

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        self.close()


def _to_item(raw: dict[str, Any], folder: str) -> DriveItem:
    return DriveItem(
        id=raw["id"],
        name=raw["name"],
        path=f"/{folder}/{raw['name']}" if folder else f"/{raw['name']}",
        is_folder="folder" in raw,
        size=raw.get("size", 0),
        modified_at=datetime.fromisoformat(raw["lastModifiedDateTime"]),
    )
