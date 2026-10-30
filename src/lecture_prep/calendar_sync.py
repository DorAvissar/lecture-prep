"""Decide which of the day's calendar events are lectures, and of which course."""

from dataclasses import dataclass
from datetime import date
from zoneinfo import ZoneInfo

from lecture_prep.db.models import Course
from lecture_prep.google_api.calendar import CalendarClient, CalendarEvent

# Events whose title contains one of these words are not lectures, even when they name a course.
NOT_LECTURE_WORDS = ("תרגול",)  # e.g. "תרגול - חדוא 2"


@dataclass(frozen=True)
class ScheduledLecture:
    course: Course
    event: CalendarEvent


def match_course(event_title: str, courses: list[Course]) -> Course | None:
    """Return the course whose name or one of its aliases appears in the event title, or None.

    - Matching ignores upper/lower case.
    - Empty names never match.
    """
    for course in courses:
        names = [course.name] + course.aliases
        for name in names:
            if name != "" and name.lower() in event_title.lower():
                return course
    return None


def lectures_on(
    calendar: CalendarClient, courses: list[Course], day: date, tz: ZoneInfo
) -> list[ScheduledLecture]:
    """The day's lectures: calendar events that match a course, keeping the calendar's order."""
    lectures = []
    for event in calendar.events_on(day, tz):
        if any(word in event.title for word in NOT_LECTURE_WORDS):
            continue
        course = match_course(event.title, courses)
        if course is not None:
            lectures.append(ScheduledLecture(course=course, event=event))
    return lectures
