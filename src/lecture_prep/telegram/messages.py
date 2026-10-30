"""Turn summaries into Telegram messages.

Claude writes markdown; Telegram understands only a small HTML subset, so headings and bold become <b>,
inline code becomes <code>, list dashes become bullets, and everything else is escaped.
"""

import html
import re
from zoneinfo import ZoneInfo

from lecture_prep.daily import LectureBrief
from lecture_prep.telegram.client import MAX_MESSAGE_LENGTH

HEADING = re.compile(r"^#{1,6}\s+(.+)$")
BULLET = re.compile(r"^(\s*)[-*]\s+")
BOLD = re.compile(r"\*\*(.+?)\*\*")
CODE = re.compile(r"`([^`]+)`")


def markdown_to_html(markdown: str) -> str:
    lines = []
    for line in markdown.strip().splitlines():
        line = html.escape(line, quote=False)
        if heading := HEADING.match(line):
            line = f"<b>{heading.group(1)}</b>"
        line = BULLET.sub(r"\1• ", line)
        line = BOLD.sub(r"<b>\1</b>", line)
        line = CODE.sub(r"<code>\1</code>", line)
        lines.append(line)
    return "\n".join(lines)


def split_message(text: str, limit: int = MAX_MESSAGE_LENGTH) -> list[str]:
    """Split at line breaks so each part fits Telegram's limit. Tags never span lines, so they stay whole."""
    parts: list[str] = []
    current = ""
    for line in text.split("\n"):
        while len(line) > limit:  # a single huge line: cut it hard
            parts.append(line[:limit])
            line = line[limit:]
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > limit:
            parts.append(current)
            candidate = line
        current = candidate
    if current.strip():
        parts.append(current)
    return parts


def lecture_heading(brief: LectureBrief, tz: ZoneInfo) -> str:
    start = brief.event.start.astimezone(tz)
    return f"{start:%H:%M}  {html.escape(brief.course.name)} - הרצאה {brief.number}"


def morning_messages(briefs: list[LectureBrief], tz: ZoneInfo) -> list[str]:
    """An overview of the day, then the recap and the prep brief of every lecture."""
    overview = "<b>📚 ההרצאות של היום</b>\n" + "\n".join(f"• {lecture_heading(b, tz)}" for b in briefs)
    messages = [overview]
    for brief in briefs:
        name = html.escape(brief.course.name)
        if brief.recap is not None:
            title = f"<b>🔁 חזרה: {name}, הרצאה {brief.number - 1}</b>"
            messages += split_message(f"{title}\n\n{markdown_to_html(brief.recap.content)}")
        if brief.prep is not None:
            title = f"<b>💡 הכנה: {name}, הרצאה {brief.number}</b>"
            messages += split_message(f"{title}\n\n{markdown_to_html(brief.prep.content)}")
        else:
            messages.append(f"<b>💡 הכנה: {name}, הרצאה {brief.number}</b>\n\nאין עדיין קבצים להרצאה הזאת.")
    return messages


def reminder_message(brief: LectureBrief, tz: ZoneInfo) -> str:
    return f"⏰ <b>עוד מעט:</b> {lecture_heading(brief, tz)}"
