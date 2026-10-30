"""Decide which of the day's calendar events are lectures, and of which course.

Exercise: `match_course` and `lectures_on` are yours to implement - see tests/test_calendar_sync.py.
"""

from dataclasses import dataclass
from datetime import date
from zoneinfo import ZoneInfo

from lecture_prep.db.models import Course
from lecture_prep.google_api.calendar import CalendarClient, CalendarEvent


@dataclass(frozen=True)
class ScheduledLecture:
    course: Course
    event: CalendarEvent


def match_course(event_title: str, courses: list[Course]) -> Course | None:
    """Return the course whose name or one of its aliases appears in the event title, or None.

    - Matching ignores upper/lower case.
    - If several courses match, the longest matching name wins ("Linear Algebra 2" beats "Linear Algebra").
    - Empty names never match.
    """
    raise NotImplementedError("Task 1 - yours to write")


def lectures_on(
    calendar: CalendarClient, courses: list[Course], day: date, tz: ZoneInfo
) -> list[ScheduledLecture]:
    """The day's lectures: calendar events that match a course, keeping the calendar's order."""
    raise NotImplementedError("Task 3 - yours to write")
