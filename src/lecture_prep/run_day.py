"""Run the daily pipeline once and print the summaries - the whole flow, without Telegram.

uv run python -m lecture_prep.run_day               # today
uv run python -m lecture_prep.run_day 2026-11-02    # another day
"""

import sys
from datetime import date, datetime
from zoneinfo import ZoneInfo

from lecture_prep.config import get_settings
from lecture_prep.daily import LectureBrief, prepare_day
from lecture_prep.db.session import SessionLocal
from lecture_prep.google_api.calendar import CalendarClient
from lecture_prep.google_api.drive import DriveClient
from lecture_prep.summarizer import Summarizer, claude_client


def main() -> None:
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    day = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else datetime.now(tz).date()
    api_key = settings.anthropic_api_key.get_secret_value() if settings.anthropic_api_key else None
    writer = Summarizer(claude_client(api_key), settings.anthropic_model)

    with (
        CalendarClient.from_settings(settings) as calendar,
        DriveClient.from_settings(settings) as drive,
        SessionLocal() as session,
    ):
        briefs = prepare_day(session, calendar, drive, writer, day, tz)

    if not briefs:
        print(f"No lectures on {day}.")
    for brief in briefs:
        print_brief(brief, tz)


def print_brief(brief: LectureBrief, tz: ZoneInfo) -> None:
    print("=" * 70)
    print(f"{brief.course.name}  lecture {brief.number}  {brief.event.start.astimezone(tz):%H:%M}")
    for title, summary in (("Recap", brief.recap), ("Prep", brief.prep)):
        print(f"\n--- {title} ---")
        print(summary.content if summary else "(no material)")


if __name__ == "__main__":
    main()
