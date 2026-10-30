from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from lecture_prep.daily import LectureBrief
from lecture_prep.db.models import Course, Summary, SummaryKind
from lecture_prep.google_api.calendar import CalendarEvent
from lecture_prep.telegram.messages import markdown_to_html, morning_messages, reminder_message, split_message

TZ = ZoneInfo("Asia/Jerusalem")


def brief(
    name: str = "חדוא 2", number: int = 5, recap: str | None = "r", prep: str | None = "p"
) -> LectureBrief:
    start = datetime(2026, 11, 2, 10, 15, tzinfo=TZ)
    return LectureBrief(
        course=Course(name=name, drive_folder="x"),
        event=CalendarEvent(id="e1", title=name, start=start, end=start + timedelta(hours=2)),
        number=number,
        recap=Summary(kind=SummaryKind.RECAP, content=recap, model="m") if recap else None,
        prep=Summary(kind=SummaryKind.PREP, content=prep, model="m") if prep else None,
    )


def test_markdown_becomes_telegram_html():
    markdown = "## נגזרות\n\n- **שיפוע** של `f(x)`\n* a < b & c"

    assert markdown_to_html(markdown) == (
        "<b>נגזרות</b>\n\n• <b>שיפוע</b> של <code>f(x)</code>\n• a &lt; b &amp; c"
    )


def test_split_message_keeps_short_text_whole():
    assert split_message("one\ntwo", limit=100) == ["one\ntwo"]


def test_split_message_breaks_at_lines():
    assert split_message("aaaa\nbbbb\ncccc", limit=9) == ["aaaa\nbbbb", "cccc"]


def test_split_message_cuts_a_line_longer_than_the_limit():
    assert split_message("x" * 12, limit=5) == ["xxxxx", "xxxxx", "xx"]


def test_morning_messages_start_with_an_overview_then_recap_and_prep():
    overview, recap, prep = morning_messages([brief()], TZ)

    assert "10:15  חדוא 2 - הרצאה 5" in overview
    assert recap.startswith("<b>🔁 חזרה: חדוא 2, הרצאה 4</b>")
    assert prep.startswith("<b>💡 הכנה: חדוא 2, הרצאה 5</b>")


def test_morning_messages_say_when_prep_material_is_missing():
    overview, prep = morning_messages([brief(recap=None, prep=None)], TZ)

    assert "אין עדיין קבצים" in prep


def test_course_names_are_escaped():
    [overview, *_] = morning_messages([brief(name="C<D>")], TZ)

    assert "C&lt;D&gt;" in overview


def test_reminder_names_the_lecture():
    assert "חדוא 2 - הרצאה 5" in reminder_message(brief(), TZ)
