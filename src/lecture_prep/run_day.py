"""Run the daily pipeline once and print the summaries - the whole flow, without Telegram.

uv run python -m lecture_prep.run_day               # today
uv run python -m lecture_prep.run_day 2026-11-02    # another day
"""

import logging
import sys
from datetime import date, datetime
from zoneinfo import ZoneInfo

from lecture_prep.config import get_settings
from lecture_prep.daily import LectureBrief, prepare_day
from lecture_prep.db.session import SessionLocal
from lecture_prep.google_api.calendar import CalendarClient
from lecture_prep.google_api.drive import DriveClient
from lecture_prep.llm import make_model
from lecture_prep.summarizer import Summarizer


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    for noisy in ("httpx", "anthropic"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    day = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else datetime.now(tz).date()
    writer = Summarizer(make_model(settings))

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
