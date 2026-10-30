"""The tick address: password check, and one tick at a time."""

import pytest
from fastapi.testclient import TestClient

from lecture_prep.config import Settings, get_settings
from lecture_prep.main import create_app
from lecture_prep.web import internal


@pytest.fixture
def runs(monkeypatch) -> list[Settings]:
    calls: list[Settings] = []
    monkeypatch.setattr(internal, "run_once", lambda settings: calls.append(settings) or [])
    return calls


def client(tick_secret: str | None = "s3cret") -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, tick_secret=tick_secret)
    return TestClient(app)


def test_the_right_secret_starts_a_tick(runs):
    response = client().post("/internal/tick", headers={"X-Tick-Secret": "s3cret"})

    assert response.status_code == 202
    assert response.json() == {"status": "started"}
    assert len(runs) == 1


def test_a_wrong_or_missing_secret_is_refused(runs):
    assert client().post("/internal/tick", headers={"X-Tick-Secret": "nope"}).status_code == 401
    assert client().post("/internal/tick").status_code == 401
    assert runs == []


def test_without_a_configured_secret_the_address_is_closed(runs):
    response = client(tick_secret=None).post("/internal/tick", headers={"X-Tick-Secret": "x"})

    assert response.status_code == 503


def test_a_tick_already_running_is_not_started_again(runs):
    assert internal._running.acquire(blocking=False)
    try:
        response = client().post("/internal/tick", headers={"X-Tick-Secret": "s3cret"})
    finally:
        internal._running.release()

    assert response.json() == {"status": "already running"}
    assert runs == []


def test_render_external_url_is_used_as_the_public_url(monkeypatch):
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://lecture-prep.onrender.com")

    assert Settings(_env_file=None).public_url == "https://lecture-prep.onrender.com"
