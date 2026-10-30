"""Daily pipeline tests: fake calendar, Drive and summary writer, real database."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fakes import FakeDrive, FakeWriter, pdf
from sqlalchemy.orm import Session

from lecture_prep.daily import prepare_day
from lecture_prep.db.models import Course, SummaryKind
from lecture_prep.google_api.calendar import CalendarEvent

TZ = ZoneInfo("Asia/Jerusalem")
MONDAY = date(2026, 11, 2)


class FakeCalendar:
    def __init__(self, *titles: str) -> None:
        self.titles = titles

    def events_on(self, day: date, tz: ZoneInfo) -> list[CalendarEvent]:
        start = datetime(day.year, day.month, day.day, 10, tzinfo=tz)
        return [
            CalendarEvent(id=f"e{i}", title=title, start=start, end=start + timedelta(hours=2))
            for i, title in enumerate(self.titles)
        ]


ALL_LECTURES = [pdf("1.pdf"), pdf("2 slides.pdf"), pdf("2 notes.pdf"), pdf("3.pdf"), pdf("4.pdf")]
NEXT_WEEK = MONDAY + timedelta(7)


@pytest.fixture
def calculus(db_session: Session) -> Course:
    course = Course(name="Calculus", aliases=["חדוא"], drive_folder="Lectures/Calculus", start_lecture=2)
    db_session.add(course)
    db_session.commit()
    return course


def run(db_session, day=MONDAY, title="חדוא - הרצאה", drive=None, writer=None):
    drive = drive or FakeDrive(*ALL_LECTURES)
    writer = writer or FakeWriter()
    return prepare_day(db_session, FakeCalendar(title), drive, writer, day, TZ), writer


def test_first_run_starts_at_start_lecture(db_session, calculus):
    [brief], writer = run(db_session)

    assert brief.course is calculus
    assert brief.number == 2
    assert brief.prep is not None and brief.prep.content == "prep of 2 notes.pdf"
    assert brief.recap is not None and brief.recap.content == "recap of 1.pdf"
    assert writer.calls == [
        (SummaryKind.PREP, ["2 notes.pdf", "2 slides.pdf"]),
        (SummaryKind.RECAP, ["1.pdf"]),
    ]


def test_each_lecture_day_moves_one_lecture_forward(db_session, calculus):
    run(db_session)

    [brief], _ = run(db_session, day=NEXT_WEEK)

    assert brief.number == 3
    assert brief.prep is not None and brief.prep.content == "prep of 3.pdf"
    assert brief.recap is not None and brief.recap.content == "recap of 2 notes.pdf"
    assert [(lecture.number, lecture.held_on) for lecture in calculus.lectures] == [
        (1, None),
        (2, MONDAY),
        (3, NEXT_WEEK),
    ]


def test_a_second_run_on_the_same_day_reuses_everything(db_session, calculus):
    writer = FakeWriter()
    run(db_session, writer=writer)

    [brief], _ = run(db_session, writer=writer)

    assert brief.number == 2
    assert len(writer.calls) == 2


def test_days_without_the_course_do_not_count(db_session, calculus):
    run(db_session)
    run(db_session, day=MONDAY + timedelta(1), title="Dentist")

    [brief], _ = run(db_session, day=NEXT_WEEK)

    assert brief.number == 3


def test_a_raised_start_lecture_skips_ahead(db_session, calculus):
    run(db_session)
    calculus.start_lecture = 4
    db_session.commit()

    [brief], _ = run(db_session, day=NEXT_WEEK)

    assert brief.number == 4


def test_lecture_without_files_has_no_prep(db_session, calculus):
    [brief], _ = run(db_session, drive=FakeDrive(pdf("1.pdf")))

    assert brief.number == 2
    assert brief.prep is None
    assert brief.recap is not None


def test_first_lecture_of_the_course_has_no_recap(db_session, calculus):
    calculus.start_lecture = 1
    db_session.commit()

    [brief], _ = run(db_session)

    assert brief.prep is not None
    assert brief.recap is None


def test_tutorials_and_other_events_are_ignored(db_session, calculus):
    writer = FakeWriter()

    assert run(db_session, title="תרגול - חדוא", writer=writer)[0] == []
    assert run(db_session, title="Dentist", writer=writer)[0] == []
    assert writer.calls == []
