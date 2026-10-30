"""The test send: the morning message goes out now, and the real one still goes out on the day."""

from datetime import timedelta
from zoneinfo import ZoneInfo

import pytest
from fakes import FakeDrive, FakeWriter, pdf
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_tick import LECTURE_START, SCHEDULE, FakeCalendar, FakeTelegram

from lecture_prep.db.models import Course, SentMessage
from lecture_prep.send_test import TEST_MARK, send_test
from lecture_prep.tick import tick

TZ = ZoneInfo("Asia/Jerusalem")


@pytest.fixture
def calculus(db_session: Session) -> Course:
    course = Course(name="Calculus", aliases=[], drive_folder="Lectures/Calculus", start_lecture=2)
    db_session.add(course)
    db_session.commit()
    return course


def test_sends_a_marked_morning_message_and_records_nothing(db_session, calculus):
    telegram = FakeTelegram()
    drive = FakeDrive(pdf("1.pdf"), pdf("2.pdf"))

    count = send_test(
        db_session,
        FakeCalendar("Calculus"),
        drive,
        FakeWriter(),
        telegram,
        99,
        LECTURE_START.date(),
        TZ,
        "https://app.example.com",
    )

    assert count == 1
    [(chat_id, text, buttons)] = telegram.sent
    assert text.startswith(TEST_MARK)
    assert "Calculus - הרצאה 2" in text
    assert len(buttons) == 1
    assert db_session.scalars(select(SentMessage)).all() == []


def test_the_real_morning_message_still_goes_out_after_a_test(db_session, calculus):
    drive = FakeDrive(pdf("1.pdf"), pdf("2.pdf"))
    writer = FakeWriter()
    send_test(
        db_session,
        FakeCalendar("Calculus"),
        drive,
        writer,
        FakeTelegram(),
        99,
        LECTURE_START.date(),
        TZ,
        None,
    )

    morning = LECTURE_START.replace(hour=7)
    sent = tick(db_session, FakeCalendar("Calculus"), drive, writer, FakeTelegram(), 99, SCHEDULE, morning)

    assert sent == ["morning"]
    assert len(writer.calls) == 2  # the summaries written for the test were reused


def test_a_day_without_lectures_sends_nothing(db_session, calculus):
    telegram = FakeTelegram()

    count = send_test(
        db_session,
        FakeCalendar("Dentist"),
        FakeDrive(),
        FakeWriter(),
        telegram,
        99,
        LECTURE_START.date() + timedelta(1),
        TZ,
        None,
    )

    assert count == 0
    assert telegram.sent == []
