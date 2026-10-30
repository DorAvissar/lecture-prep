"""The daily run: today's lectures from the calendar -> their files in Drive -> recap and prep summaries.

Summaries are stored, so running twice on the same day costs nothing the second time.
"""

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
from lecture_prep.lecture_locator import LectureMaterial, locate
from lecture_prep.summarizer import LectureFile, SummaryResult


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
    prep: Summary | None  # None when today's material is not in Drive yet
    recap: Summary | None  # None for the course's first lecture


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
    material = locate(drive, course)
    today, before = material.current, material.previous

    if today is not None:
        lecture = get_or_create_lecture(session, course, today)
        if lecture.held_on is not None and lecture.held_on < day:
            # The newest files were already taught on an earlier day: today's material is not uploaded
            # yet. The newest lecture is then the one to recap.
            today, before = None, today
        else:
            lecture.held_on = day
            session.commit()

    return LectureBrief(
        course=course,
        event=scheduled.event,
        prep=summary_for(session, drive, writer, course, today, SummaryKind.PREP) if today else None,
        recap=summary_for(session, drive, writer, course, before, SummaryKind.RECAP) if before else None,
    )


def summary_for(
    session: Session,
    drive: Drive,
    writer: Writer,
    course: Course,
    material: LectureMaterial,
    kind: SummaryKind,
) -> Summary:
    """The stored summary of this kind, or a new one written now and saved straight away."""
    lecture = get_or_create_lecture(session, course, material)
    existing = next((summary for summary in lecture.summaries if summary.kind == kind), None)
    if existing is not None:
        return existing

    files = [LectureFile(item.name, drive.download(item)) for item in material.files]
    result = writer.summarize(kind, course.name, files)
    summary = Summary(kind=kind, content=result.content, model=result.model)
    lecture.summaries.append(summary)
    session.commit()  # each summary costs money - keep it even if a later step fails
    return summary


def get_or_create_lecture(session: Session, course: Course, material: LectureMaterial) -> Lecture:
    lecture = session.scalar(
        select(Lecture).where(Lecture.course_id == course.id, Lecture.number == material.number)
    )
    if lecture is None:
        lecture = Lecture(number=material.number, title=material.files[0].name)
        course.lectures.append(lecture)
        session.flush()
    return lecture
