"""The Telegram messages the app sends: short, with buttons that open the Mini App.

The summaries themselves are read in the Mini App, not in the chat, so a lecture day costs one morning
message and one reminder per lecture instead of a stream of long texts.
"""

import html
from zoneinfo import ZoneInfo

from lecture_prep.daily import LectureBrief
from lecture_prep.telegram.client import Button


def lecture_heading(brief: LectureBrief, tz: ZoneInfo) -> str:
    start = brief.event.start.astimezone(tz)
    return f"{start:%H:%M}  {html.escape(brief.course.name)} - הרצאה {brief.number}"


def lecture_url(app_url: str, brief: LectureBrief) -> str:
    return f"{app_url.rstrip('/')}/app?course={brief.course.id}&lecture={brief.number}"


def lecture_button(app_url: str, brief: LectureBrief) -> Button:
    return Button(f"{brief.course.name} - הרצאה {brief.number}", lecture_url(app_url, brief), web_app=True)


def morning_message(
    briefs: list[LectureBrief], tz: ZoneInfo, app_url: str | None
) -> tuple[str, list[Button]]:
    """The day's lectures, with a button per lecture that opens its prep, recap and chat."""
    lines = ["<b>📚 ההרצאות של היום</b>", *(f"• {lecture_heading(brief, tz)}" for brief in briefs)]
    if app_url is None:
        return "\n".join(lines), []
    lines += ["", "לחיצה על הרצאה פותחת את ההכנה, החזרה והשאלות."]
    return "\n".join(lines), [lecture_button(app_url, brief) for brief in briefs]


def reminder_message(brief: LectureBrief, tz: ZoneInfo, app_url: str | None) -> tuple[str, list[Button]]:
    text = f"⏰ <b>עוד מעט:</b> {lecture_heading(brief, tz)}"
    return text, [lecture_button(app_url, brief)] if app_url else []
