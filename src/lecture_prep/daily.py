"""The daily run: today's lectures from the calendar -> their files in Drive -> recap and prep summaries.

Lectures are counted, not guessed from the files: a course starts at its start_lecture, and each day
the course is on the calendar moves it one lecture forward. Summaries are stored, so running twice on
the same day costs nothing the second time.
"""

import logging
from dataclasses import dataclass
from datetime import date
from typing import Protocol
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from lecture_prep.calendar_sync import ScheduledLecture, lectures_on
from lecture_prep.db.models import Course, Lecture, Summary, SummaryKind
from lecture_prep.google_api.calendar import CalendarClient, CalendarEvent
from lecture_prep.google_api.drive import DriveItem
from lecture_prep.lecture_locator import LectureMaterial, course_lectures
from lecture_prep.summarizer import LectureFile, SummaryResult

log = logging.getLogger(__name__)


class Drive(Protocol):
    def list_folder(self, path: str) -> list[DriveItem]: ...
    def download(self, item: DriveItem) -> bytes: ...


class Writer(Protocol):
    """Anything that writes summaries - the real Summarizer, or a fake in tests."""

    def summarize(self, kind: SummaryKind, course_name: str, files: list[LectureFile]) -> SummaryResult: ...


@dataclass(frozen=True)
class LectureBrief:
    course: Course
    event: CalendarEvent
    number: int  # today's lecture number
    prep: Summary | None  # None when today's lecture has no files in Drive
    recap: Summary | None  # None when the previous lecture has no files (or this is lecture 1)


def prepare_day(
    session: Session, calendar: CalendarClient, drive: Drive, writer: Writer, day: date, tz: ZoneInfo
) -> list[LectureBrief]:
    courses = list(session.scalars(select(Course).order_by(Course.name)))
    return [
        prepare_lecture(session, drive, writer, scheduled, day)
        for scheduled in lectures_on(calendar, courses, day, tz)
    ]


def prepare_lecture(
    session: Session, drive: Drive, writer: Writer, scheduled: ScheduledLecture, day: date
) -> LectureBrief:
    course = scheduled.course
    number = todays_number(session, course, day)
    get_or_create_lecture(session, course, number).held_on = day
    session.commit()

    lectures = course_lectures(drive, course)
    today, before = lectures.get(number), lectures.get(number - 1)
    if today is None:
        log.warning("No files for lecture %d of %s in Drive", number, course.name)

    return LectureBrief(
        course=course,
        event=scheduled.event,
        number=number,
        prep=summary_for(session, drive, writer, course, today, SummaryKind.PREP) if today else None,
        recap=summary_for(session, drive, writer, course, before, SummaryKind.RECAP) if before else None,
    )


def todays_number(session: Session, course: Course, day: date) -> int:
    """The lecture taught on `day`: one past the last lecture taught before it, never below start_lecture.

    A lecture already marked for `day` keeps its number, so a second run (or a double session) on the
    same day does not move the count.
    """
    held = session.execute(
        select(Lecture.number, Lecture.held_on).where(
            Lecture.course_id == course.id, Lecture.held_on.is_not(None)
        )
    ).all()
    for number, held_on in held:
        if held_on == day:
            return number
    earlier = [number for number, held_on in held if held_on < day]
    return max([course.start_lecture, *(number + 1 for number in earlier)])


def summary_for(
    session: Session,
    drive: Drive,
    writer: Writer,
    course: Course,
    material: LectureMaterial,
    kind: SummaryKind,
) -> Summary:
    """The stored summary of this kind, or a new one written now and saved straight away."""
    lecture = get_or_create_lecture(session, course, material.number)
    lecture.title = material.files[0].name
    existing = next((summary for summary in lecture.summaries if summary.kind == kind), None)
    if existing is not None:
        return existing

    files = [LectureFile(item.name, drive.download(item)) for item in material.files]
    result = writer.summarize(kind, course.name, files)
    summary = Summary(kind=kind, content=result.content, model=result.model)
    lecture.summaries.append(summary)
    session.commit()  # each summary costs money - keep it even if a later step fails
    return summary


def get_or_create_lecture(session: Session, course: Course, number: int) -> Lecture:
    lecture = session.scalar(select(Lecture).where(Lecture.course_id == course.id, Lecture.number == number))
    if lecture is None:
        lecture = Lecture(number=number)
        course.lectures.append(lecture)
        session.flush()
    return lecture
