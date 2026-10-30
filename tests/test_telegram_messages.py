from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from lecture_prep.daily import LectureBrief
from lecture_prep.db.models import Course
from lecture_prep.google_api.calendar import CalendarEvent
from lecture_prep.telegram.client import Button
from lecture_prep.telegram.messages import morning_message, reminder_message

TZ = ZoneInfo("Asia/Jerusalem")
APP = "https://lecture-prep.example.com/"


def brief(name: str = "חדוא 2", course_id: int = 3, number: int = 5) -> LectureBrief:
    start = datetime(2026, 11, 2, 10, 15, tzinfo=TZ)
    return LectureBrief(
        course=Course(id=course_id, name=name, drive_folder="x"),
        event=CalendarEvent(id="e1", title=name, start=start, end=start + timedelta(hours=2)),
        number=number,
        recap=None,
        prep=None,
    )


def test_morning_message_lists_lectures_with_a_button_each():
    text, buttons = morning_message([brief(), brief("Systems", 4, 7)], TZ, APP)

    assert "10:15  חדוא 2 - הרצאה 5" in text
    assert buttons == [
        Button("חדוא 2 - הרצאה 5", "https://lecture-prep.example.com/app?course=3&lecture=5", web_app=True),
        Button("Systems - הרצאה 7", "https://lecture-prep.example.com/app?course=4&lecture=7", web_app=True),
    ]


def test_without_an_app_url_there_are_no_buttons():
    text, buttons = morning_message([brief()], TZ, None)

    assert "חדוא 2" in text
    assert buttons == []


def test_course_names_are_escaped():
    text, _ = morning_message([brief(name="C<D>")], TZ, APP)

    assert "C&lt;D&gt;" in text


def test_reminder_names_the_lecture_and_opens_it():
    text, [button] = reminder_message(brief(), TZ, APP)

    assert "חדוא 2 - הרצאה 5" in text
    assert button.web_app
