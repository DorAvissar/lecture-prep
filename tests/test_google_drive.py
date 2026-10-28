"""Drive client tests. httpx.MockTransport plays the role of Google Drive - no network, no account."""

from collections.abc import Callable
from datetime import UTC, datetime

import httpx
import pytest

from lecture_prep.google_api.auth import BearerAuth
from lecture_prep.google_api.drive import DRIVE_URL, FOLDER_MIME, DriveClient, DriveItem, FolderNotFoundError

Handler = Callable[[httpx.Request], httpx.Response]
PDF = "application/pdf"


def make_client(handler: Handler) -> DriveClient:
    http = httpx.Client(
        base_url=DRIVE_URL, transport=httpx.MockTransport(handler), auth=BearerAuth(lambda: "test-token")
    )
    return DriveClient(http)


def drive_file(file_id: str, name: str, mime_type: str = PDF) -> dict:
    return {
        "id": file_id,
        "name": name,
        "mimeType": mime_type,
        "size": "1234",
        "modifiedTime": "2026-10-20T08:15:00.000Z",
    }


def files(*items: dict, next_page: str | None = None) -> httpx.Response:
    body: dict = {"files": list(items)}
    if next_page:
        body["nextPageToken"] = next_page
    return httpx.Response(200, json=body)


def test_list_root():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-token"
        assert request.url.params["q"] == "'root' in parents and trashed = false"
        return files(drive_file("f1", "Lectures", FOLDER_MIME))

    [item] = make_client(handler).list_folder("/")

    assert item.path == "/Lectures"
    assert item.is_folder
    assert item.size == 1234
    assert item.modified_at == datetime(2026, 10, 20, 8, 15, tzinfo=UTC)


def test_nested_path_is_resolved_folder_by_folder():
    queries: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        query = request.url.params["q"]
        queries.append(query)
        if "name = 'Lectures'" in query:
            return files(drive_file("lectures-id", "Lectures", FOLDER_MIME))
        if "name = 'לינארית 1'" in query:
            assert query.startswith("'lectures-id' in parents")
            return files(drive_file("linear-id", "לינארית 1", FOLDER_MIME))
        assert query.startswith("'linear-id' in parents")
        return files(drive_file("p1", "הרצאה 1.pdf"))

    [item] = make_client(handler).list_folder("Lectures/לינארית 1/")

    assert len(queries) == 3
    assert item.path == "/Lectures/לינארית 1/הרצאה 1.pdf"
    assert not item.is_folder


def test_quotes_in_folder_names_are_escaped():
    def handler(request: httpx.Request) -> httpx.Response:
        query = request.url.params["q"]
        if "name = " in query:
            assert "name = 'Dor\\'s notes'" in query
            return files(drive_file("notes-id", "Dor's notes", FOLDER_MIME))
        return files()

    assert make_client(handler).list_folder("Dor's notes") == []


def test_missing_folder_raises_folder_not_found():
    with pytest.raises(FolderNotFoundError):
        make_client(lambda request: files()).list_folder("No/Such/Folder")


def test_listing_follows_pagination():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("pageToken") == "page-2":
            return files(drive_file("b", "b.pdf"))
        return files(drive_file("a", "a.pdf"), next_page="page-2")

    items = make_client(handler).list_folder("")

    assert [item.name for item in items] == ["a.pdf", "b.pdf"]


def item(mime_type: str) -> DriveItem:
    return DriveItem(id="42", name="x", path="/x", mime_type=mime_type, size=0, modified_at=datetime.now(UTC))


def test_download_regular_file_uses_alt_media():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/drive/v3/files/42"
        assert request.url.params["alt"] == "media"
        return httpx.Response(200, content=b"%PDF-1.7 lecture")

    assert make_client(handler).download(item(PDF)) == b"%PDF-1.7 lecture"


def test_download_google_slides_exports_pdf():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/drive/v3/files/42/export"
        assert request.url.params["mimeType"] == PDF
        return httpx.Response(200, content=b"%PDF-1.7 slides")

    slides = item("application/vnd.google-apps.presentation")

    assert slides.is_google_doc
    assert make_client(handler).download(slides) == b"%PDF-1.7 slides"
