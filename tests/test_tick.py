"""Scheduler tick tests: fake calendar, Drive, writer and Telegram; real database."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fakes import FakeDrive, FakeWriter, pdf
from sqlalchemy.orm import Session

from lecture_prep.db.models import Course
from lecture_prep.google_api.calendar import CalendarEvent
from lecture_prep.telegram.client import Button
from lecture_prep.tick import Schedule, tick

TZ = ZoneInfo("Asia/Jerusalem")
SCHEDULE = Schedule(tz=TZ, morning_hour=7, reminder_minutes=30, app_url="https://app.example.com")
LECTURE_START = datetime(2026, 11, 2, 10, 0, tzinfo=TZ)


class FakeCalendar:
    def __init__(self, *titles: str) -> None:
        self.titles = titles

    def events_on(self, day, tz):
        start = LECTURE_START
        return [
            CalendarEvent(id=f"e{i}", title=title, start=start, end=start + timedelta(hours=2))
            for i, title in enumerate(self.titles)
        ]


class FakeTelegram:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str, list[Button]]] = []

    def send_message(self, chat_id: int, html: str, buttons: list[Button] | None = None) -> None:
        self.sent.append((chat_id, html, buttons or []))


@pytest.fixture
def calculus(db_session: Session) -> Course:
    course = Course(name="Calculus", aliases=[], drive_folder="Lectures/Calculus", start_lecture=2)
    db_session.add(course)
    db_session.commit()
    return course


def run(db_session, at: datetime, telegram: FakeTelegram, title: str = "Calculus") -> list[str]:
    drive = FakeDrive(pdf("1.pdf"), pdf("2.pdf"))
    return tick(db_session, FakeCalendar(title), drive, FakeWriter(), telegram, 99, SCHEDULE, at)


def test_nothing_happens_before_the_morning_hour(db_session, calculus):
    telegram = FakeTelegram()

    assert run(db_session, LECTURE_START.replace(hour=6, minute=45), telegram) == []
    assert telegram.sent == []


def test_morning_message_is_sent_once(db_session, calculus):
    telegram = FakeTelegram()

    assert run(db_session, LECTURE_START.replace(hour=7), telegram) == ["morning"]
    assert run(db_session, LECTURE_START.replace(hour=7, minute=15), telegram) == []
    [(chat_id, text, buttons)] = telegram.sent
    assert chat_id == 99
    assert "Calculus - הרצאה 2" in text
    assert [button.url for button in buttons] == [
        f"https://app.example.com/app?course={calculus.id}&lecture=2"
    ]


def test_reminder_is_sent_once_shortly_before_the_lecture(db_session, calculus):
    telegram = FakeTelegram()
    run(db_session, LECTURE_START.replace(hour=7), telegram)

    assert run(db_session, LECTURE_START - timedelta(minutes=45), telegram) == []
    assert run(db_session, LECTURE_START - timedelta(minutes=30), telegram) == ["reminder Calculus"]
    assert run(db_session, LECTURE_START - timedelta(minutes=15), telegram) == []
    assert "עוד מעט" in telegram.sent[-1][1]


def test_no_reminder_once_the_lecture_started(db_session, calculus):
    telegram = FakeTelegram()
    run(db_session, LECTURE_START.replace(hour=7), telegram)

    assert run(db_session, LECTURE_START + timedelta(minutes=5), telegram) == []


def test_days_without_lectures_send_nothing(db_session, calculus):
    telegram = FakeTelegram()

    assert run(db_session, LECTURE_START.replace(hour=8), telegram, title="Dentist") == []
    assert telegram.sent == []
