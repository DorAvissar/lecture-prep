from fastapi.testclient import TestClient

from lecture_prep import __version__
from lecture_prep.main import create_app


def test_health_returns_ok_and_version():
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__, "environment": "development"}
