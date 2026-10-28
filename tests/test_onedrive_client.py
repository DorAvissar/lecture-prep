"""OneDrive client tests. httpx.MockTransport plays the role of Microsoft Graph - no network, no account."""

from collections.abc import Callable
from datetime import UTC, datetime

import httpx
import pytest

from lecture_prep.config import Settings
from lecture_prep.onedrive.auth import BearerAuth, OneDriveAuthError
from lecture_prep.onedrive.client import GRAPH_URL, FolderNotFoundError, OneDriveClient

Handler = Callable[[httpx.Request], httpx.Response]


def make_client(handler: Handler) -> OneDriveClient:
    http = httpx.Client(
        base_url=GRAPH_URL,
        transport=httpx.MockTransport(handler),
        auth=BearerAuth(lambda: "test-token"),
        follow_redirects=True,
    )
    return OneDriveClient(http)


def graph_item(item_id: str, name: str, *, folder: bool = False) -> dict:
    item = {"id": item_id, "name": name, "size": 1234, "lastModifiedDateTime": "2026-10-20T08:15:00Z"}
    if folder:
        item["folder"] = {"childCount": 3}
    else:
        item["file"] = {"mimeType": "application/pdf"}
    return item


def test_list_root_folder():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1.0/me/drive/root/children"
        assert request.headers["Authorization"] == "Bearer test-token"
        return httpx.Response(200, json={"value": [graph_item("1", "Uni", folder=True)]})

    [item] = make_client(handler).list_folder("/")

    assert item.name == "Uni"
    assert item.path == "/Uni"
    assert item.is_folder
    assert item.modified_at == datetime(2026, 10, 20, 8, 15, tzinfo=UTC)


def test_list_nested_folder_with_spaces_and_hebrew():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.raw_path.decode() == (
            "/v1.0/me/drive/root:/Uni/%D7%9C%D7%99%D7%A0%D7%90%D7%A8%D7%99%D7%AA%201:/children"
        )
        return httpx.Response(200, json={"value": [graph_item("7", "lecture1.pdf")]})

    [item] = make_client(handler).list_folder("/Uni/לינארית 1/")

    assert item.path == "/Uni/לינארית 1/lecture1.pdf"
    assert not item.is_folder


def test_list_folder_follows_pagination():
    next_link = f"{GRAPH_URL}/me/drive/root:/Uni:/children?$skiptoken=abc"

    def handler(request: httpx.Request) -> httpx.Response:
        if "skiptoken" in str(request.url):
            return httpx.Response(200, json={"value": [graph_item("2", "b.pdf")]})
        return httpx.Response(200, json={"value": [graph_item("1", "a.pdf")], "@odata.nextLink": next_link})

    items = make_client(handler).list_folder("Uni")

    assert [item.name for item in items] == ["a.pdf", "b.pdf"]


def test_missing_folder_raises_folder_not_found():
    client = make_client(lambda request: httpx.Response(404, json={"error": {"code": "itemNotFound"}}))

    with pytest.raises(FolderNotFoundError):
        client.list_folder("/No/Such/Folder")


def test_download_follows_redirect_without_leaking_the_token():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "graph.microsoft.com":
            assert request.url.path == "/v1.0/me/drive/items/42/content"
            return httpx.Response(302, headers={"Location": "https://files.example.net/download/42"})
        assert "Authorization" not in request.headers
        return httpx.Response(200, content=b"%PDF-1.7 lecture")

    assert make_client(handler).download("42") == b"%PDF-1.7 lecture"


def test_from_settings_requires_a_client_id():
    with pytest.raises(OneDriveAuthError, match="MS_CLIENT_ID"):
        OneDriveClient.from_settings(Settings(ms_client_id=""))
