"""Spec for Task 1 (match_course) and Task 3 (lectures_on). No database or network needed."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from lecture_prep.calendar_sync import ScheduledLecture, lectures_on, match_course
from lecture_prep.db.models import Course
from lecture_prep.google_api.calendar import CalendarEvent

TZ = ZoneInfo("Asia/Jerusalem")


def course(name: str, *aliases: str) -> Course:
    return Course(name=name, aliases=list(aliases), drive_folder=f"Lectures/{name}")


LINEAR = course("אלגברה לינארית", "לינארית", "Linear Algebra")
DATA_STRUCTURES = course("מבני נתונים", "Data Structures")
COURSES = [LINEAR, DATA_STRUCTURES]


# --- Task 1: match_course ---------------------------------------------------------------------------


def test_matches_an_alias_inside_a_hebrew_title():
    assert match_course("לינארית - הרצאה 5", COURSES) is LINEAR


def test_matches_the_course_name_itself():
    assert match_course("הרצאה: מבני נתונים", COURSES) is DATA_STRUCTURES


def test_matching_ignores_case():
    assert match_course("LINEAR ALGEBRA lecture", COURSES) is LINEAR


def test_returns_none_when_nothing_matches():
    assert match_course("ארוחת צהריים עם סבתא", COURSES) is None


def test_empty_alias_never_matches():
    sloppy = course("פיזיקה", "")

    assert match_course("ארוחת צהריים", [sloppy]) is None


# --- Task 3: lectures_on ----------------------------------------------------------------------------


class FakeCalendar:
    """Stands in for CalendarClient: returns fixed events and records what it was asked."""

    def __init__(self, events: list[CalendarEvent]) -> None:
        self.events = events
        self.asked: list[tuple[date, ZoneInfo]] = []

    def events_on(self, day: date, tz: ZoneInfo) -> list[CalendarEvent]:
        self.asked.append((day, tz))
        return self.events


def event(event_id: str, title: str, hour: int) -> CalendarEvent:
    return CalendarEvent(
        id=event_id,
        title=title,
        start=datetime(2026, 11, 2, hour, tzinfo=TZ),
        end=datetime(2026, 11, 2, hour + 2, tzinfo=TZ),
    )


def test_lectures_on_keeps_only_events_that_match_a_course():
    lunch = event("e1", "ארוחת צהריים", 12)
    linear = event("e2", "לינארית - הרצאה", 14)
    calendar = FakeCalendar([lunch, linear])

    lectures = lectures_on(calendar, COURSES, date(2026, 11, 2), TZ)

    assert lectures == [ScheduledLecture(course=LINEAR, event=linear)]
    assert calendar.asked == [(date(2026, 11, 2), TZ)]


def test_lectures_on_keeps_calendar_order():
    morning = event("e1", "Data Structures", 9)
    afternoon = event("e2", "Linear Algebra", 15)

    lectures = lectures_on(FakeCalendar([morning, afternoon]), COURSES, date(2026, 11, 2), TZ)

    assert [lecture.course for lecture in lectures] == [DATA_STRUCTURES, LINEAR]


def test_lectures_on_an_empty_day():
    assert lectures_on(FakeCalendar([]), COURSES, date(2026, 11, 2), TZ) == []


def test_lectures_on_skips_tutorials_of_a_course():
    tutorial = event("e1", "תרגול - לינארית", 10)
    lecture = event("e2", "לינארית", 14)

    lectures = lectures_on(FakeCalendar([tutorial, lecture]), COURSES, date(2026, 11, 2), TZ)

    assert lectures == [ScheduledLecture(course=LINEAR, event=lecture)]
