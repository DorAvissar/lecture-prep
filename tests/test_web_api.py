"""Mini App API tests: real database, fake Drive and chat, real Telegram signature checks."""

import json
from datetime import UTC, datetime
from urllib.parse import urlencode

import pytest
from fakes import FakeDrive, pdf
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from lecture_prep.config import Settings, get_settings
from lecture_prep.db.models import Course, Lecture, Summary, SummaryKind
from lecture_prep.db.session import get_session
from lecture_prep.main import create_app
from lecture_prep.web.api import get_chat, get_drive
from lecture_prep.web.telegram_auth import signature

TOKEN = "123:secret"
OWNER = 42


class FakeChat:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def answer(self, course_name, number, current, previous, history):
        self.calls.append(
            {"current": [f.name for f in current], "previous": [f.name for f in previous], "history": history}
        )
        return "**מצביע** הוא `pointer`"


def init_data(user_id: int = OWNER) -> str:
    fields = {"auth_date": str(int(datetime.now(UTC).timestamp())), "user": json.dumps({"id": user_id})}
    return urlencode({**fields, "hash": signature(fields, TOKEN)})


@pytest.fixture
def course(db_session: Session) -> Course:
    course = Course(name="תכנות מערכות", drive_folder="Lectures/Systems")
    course.lectures = [
        Lecture(
            number=4, summaries=[Summary(kind=SummaryKind.RECAP, content="### חזרה\nעל `Heap`", model="m")]
        ),
        Lecture(number=5, summaries=[Summary(kind=SummaryKind.PREP, content="### הכנה\nטקסט", model="m")]),
    ]
    db_session.add(course)
    db_session.commit()
    return course


@pytest.fixture
def chat() -> FakeChat:
    return FakeChat()


def make_client(db_session: Session, chat: FakeChat, environment: str = "production") -> TestClient:
    app = create_app()
    settings = Settings(
        _env_file=None, environment=environment, telegram_bot_token=TOKEN, telegram_chat_id=OWNER
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_drive] = lambda: FakeDrive(
        pdf("הרצאה 4.pdf"), pdf("הרצאה 5.pdf"), folder="Lectures/Systems/הרצאות"
    )
    app.dependency_overrides[get_chat] = lambda: chat
    return TestClient(app)


def test_page_is_served(db_session, chat):
    response = make_client(db_session, chat).get("/app")

    assert response.status_code == 200
    assert 'dir="rtl"' in response.text


def test_lecture_shows_prep_and_recap_of_the_previous_lecture(db_session, course, chat):
    client = make_client(db_session, chat)

    response = client.get(f"/api/lectures/{course.id}/5", headers={"X-Telegram-Init-Data": init_data()})

    assert response.status_code == 200
    body = response.json()
    assert body["course"] == "תכנות מערכות"
    assert body["prep"] == "<h3>הכנה</h3>\n<p>טקסט</p>"
    assert "<code>Heap</code>" in body["recap"]


def test_requests_without_telegram_data_are_refused(db_session, course, chat):
    response = make_client(db_session, chat).get(f"/api/lectures/{course.id}/5")

    assert response.status_code == 401


def test_other_telegram_users_are_refused(db_session, course, chat):
    headers = {"X-Telegram-Init-Data": init_data(user_id=7)}

    response = make_client(db_session, chat).get(f"/api/lectures/{course.id}/5", headers=headers)

    assert response.status_code == 403


def test_development_allows_a_plain_browser(db_session, course, chat):
    response = make_client(db_session, chat, environment="development").get(f"/api/lectures/{course.id}/5")

    assert response.status_code == 200


def test_chat_sends_both_lectures_and_returns_html(db_session, course, chat):
    client = make_client(db_session, chat)
    body = {"course_id": course.id, "number": 5, "messages": [{"role": "user", "content": "מה זה מצביע?"}]}

    response = client.post("/api/chat", json=body, headers={"X-Telegram-Init-Data": init_data()})

    assert response.status_code == 200
    assert response.json()["answer"] == "<p><b>מצביע</b> הוא <code>pointer</code></p>"
    [call] = chat.calls
    assert call["current"] == ["הרצאה 5.pdf"]
    assert call["previous"] == ["הרצאה 4.pdf"]


def test_chat_about_a_lecture_without_files(db_session, course, chat):
    body = {"course_id": course.id, "number": 9, "messages": [{"role": "user", "content": "?"}]}

    response = make_client(db_session, chat).post(
        "/api/chat", json=body, headers={"X-Telegram-Init-Data": init_data()}
    )

    assert response.status_code == 404
