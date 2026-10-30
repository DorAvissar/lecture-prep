"""Daily pipeline tests: fake calendar, Drive and summary writer, real database."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.orm import Session

from lecture_prep.daily import prepare_day
from lecture_prep.db.models import Course, SummaryKind
from lecture_prep.google_api.calendar import CalendarEvent
from lecture_prep.google_api.drive import DriveItem
from lecture_prep.summarizer import LectureFile, SummaryResult

TZ = ZoneInfo("Asia/Jerusalem")
MONDAY = date(2026, 11, 2)


def pdf(name: str) -> DriveItem:
    return DriveItem(
        id=name,
        name=name,
        path=f"/Lectures/Calculus/{name}",
        mime_type="application/pdf",
        size=10,
        modified_at=datetime(2026, 10, 1, tzinfo=UTC),
    )


class FakeCalendar:
    def __init__(self, *titles: str) -> None:
        self.titles = titles

    def events_on(self, day: date, tz: ZoneInfo) -> list[CalendarEvent]:
        start = datetime(day.year, day.month, day.day, 10, tzinfo=tz)
        return [
            CalendarEvent(id=f"e{i}", title=title, start=start, end=start + timedelta(hours=2))
            for i, title in enumerate(self.titles)
        ]


class FakeDrive:
    def __init__(self, *items: DriveItem) -> None:
        self.items = list(items)
        self.downloaded: list[str] = []

    def list_folder(self, path: str) -> list[DriveItem]:
        return self.items

    def download(self, item: DriveItem) -> bytes:
        self.downloaded.append(item.name)
        return f"%PDF {item.name}".encode()


class FakeWriter:
    def __init__(self) -> None:
        self.calls: list[tuple[SummaryKind, list[str]]] = []

    def summarize(self, kind: SummaryKind, course_name: str, files: list[LectureFile]) -> SummaryResult:
        self.calls.append((kind, [file.name for file in files]))
        return SummaryResult(content=f"{kind} of {files[0].name}", model="fake-model")


@pytest.fixture
def calculus(db_session: Session) -> Course:
    course = Course(name="Calculus", aliases=["חדוא"], drive_folder="Lectures/Calculus")
    db_session.add(course)
    db_session.commit()
    return course


def test_writes_prep_for_today_and_recap_for_the_previous_lecture(db_session, calculus):
    drive = FakeDrive(pdf("01.pdf"), pdf("02 slides.pdf"), pdf("02 notes.pdf"))
    writer = FakeWriter()

    [brief] = prepare_day(db_session, FakeCalendar("חדוא - הרצאה"), drive, writer, MONDAY, TZ)

    assert brief.course is calculus
    assert brief.prep is not None and brief.prep.content == "prep of 02 notes.pdf"
    assert brief.recap is not None and brief.recap.content == "recap of 01.pdf"
    assert writer.calls == [
        (SummaryKind.PREP, ["02 notes.pdf", "02 slides.pdf"]),
        (SummaryKind.RECAP, ["01.pdf"]),
    ]
    assert [(lecture.number, lecture.held_on) for lecture in calculus.lectures] == [(1, None), (2, MONDAY)]


def test_a_second_run_reuses_stored_summaries(db_session, calculus):
    drive, writer = FakeDrive(pdf("01.pdf"), pdf("02.pdf")), FakeWriter()
    prepare_day(db_session, FakeCalendar("Calculus"), drive, writer, MONDAY, TZ)

    [brief] = prepare_day(db_session, FakeCalendar("Calculus"), drive, writer, MONDAY, TZ)

    assert len(writer.calls) == 2
    assert brief.prep is not None and brief.prep.model == "fake-model"


def test_next_week_the_old_prep_lecture_gets_a_recap(db_session, calculus):
    drive, writer = FakeDrive(pdf("01.pdf"), pdf("02.pdf")), FakeWriter()
    prepare_day(db_session, FakeCalendar("Calculus"), drive, writer, MONDAY, TZ)
    drive.items.append(pdf("03.pdf"))

    [brief] = prepare_day(db_session, FakeCalendar("Calculus"), drive, writer, MONDAY + timedelta(7), TZ)

    assert brief.prep is not None and brief.prep.content == "prep of 03.pdf"
    assert brief.recap is not None and brief.recap.content == "recap of 02.pdf"


def test_when_todays_files_are_missing_only_the_last_lecture_is_recapped(db_session, calculus):
    drive, writer = FakeDrive(pdf("01.pdf"), pdf("02.pdf")), FakeWriter()
    prepare_day(db_session, FakeCalendar("Calculus"), drive, writer, MONDAY, TZ)

    [brief] = prepare_day(db_session, FakeCalendar("Calculus"), drive, writer, MONDAY + timedelta(7), TZ)

    assert brief.prep is None
    assert brief.recap is not None and brief.recap.content == "recap of 02.pdf"


def test_first_lecture_has_prep_only(db_session, calculus):
    [brief] = prepare_day(
        db_session, FakeCalendar("Calculus"), FakeDrive(pdf("01.pdf")), FakeWriter(), MONDAY, TZ
    )

    assert brief.prep is not None
    assert brief.recap is None


def test_events_that_are_not_lectures_are_ignored(db_session, calculus):
    writer = FakeWriter()

    assert (
        prepare_day(db_session, FakeCalendar("Dentist"), FakeDrive(pdf("01.pdf")), writer, MONDAY, TZ) == []
    )
    assert writer.calls == []
