"""Send a day's morning message now, as a test, without recording it as sent:

    uv run python -m lecture_prep.send_test 2026-11-01              # to you
    uv run python -m lecture_prep.send_test 2026-11-01 --everyone   # to you and every member

It prepares the day's summaries (stored, so the real morning reuses them) and sends the morning message
with its buttons, marked as a test. Nothing is recorded in sent_messages, so the real morning message
still goes out on the day. Point DATABASE_URL and PUBLIC_URL at the cloud to test the deployed app.
"""

import argparse
import logging
from datetime import date
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from lecture_prep.config import get_settings
from lecture_prep.daily import Drive, Writer, prepare_day
from lecture_prep.db.session import SessionLocal
from lecture_prep.google_api.calendar import CalendarClient
from lecture_prep.google_api.drive import DriveClient
from lecture_prep.llm import make_model
from lecture_prep.members import recipients
from lecture_prep.summarizer import Summarizer
from lecture_prep.telegram.client import TelegramClient
from lecture_prep.telegram.messages import morning_message
from lecture_prep.tick import Messenger

TEST_MARK = "🧪 <b>בדיקה</b> - כך תיראה הודעת הבוקר"


def send_test(
    session: Session,
    calendar: CalendarClient,
    drive: Drive,
    writer: Writer,
    messenger: Messenger,
    chat_ids: list[int],
    day: date,
    tz: ZoneInfo,
    app_url: str | None,
) -> int:
    """Send `day`'s morning message to `chat_ids` now. Returns the number of lectures (0: nothing sent)."""
    briefs = prepare_day(session, calendar, drive, writer, day, tz)
    if not briefs:
        return 0
    text, buttons = morning_message(briefs, tz, app_url)
    for chat_id in chat_ids:
        messenger.send_message(chat_id, f"{TEST_MARK}\n\n{text}", buttons)
    return len(briefs)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    for noisy in ("httpx", "httpx2", "anthropic", "google_genai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(prog="python -m lecture_prep.send_test")
    parser.add_argument("day", nargs="?", type=date.fromisoformat, default=date.today())
    parser.add_argument("--everyone", action="store_true", help="send to every member too")
    args = parser.parse_args()
    settings = get_settings()
    if settings.telegram_bot_token is None or settings.telegram_chat_id is None:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID first (see the README).")
    tz = ZoneInfo(settings.timezone)

    with (
        CalendarClient.from_settings(settings) as calendar,
        DriveClient.from_settings(settings) as drive,
        TelegramClient.from_token(settings.telegram_bot_token.get_secret_value()) as telegram,
        SessionLocal() as session,
    ):
        writer = Summarizer(make_model(settings))
        owner = settings.telegram_chat_id
        chat_ids = recipients(session, owner) if args.everyone else [owner]
        count = send_test(
            session, calendar, drive, writer, telegram, chat_ids, args.day, tz, settings.public_url
        )
    if count:
        print(f"Sent a test morning message with {count} lectures to {len(chat_ids)} people.")
    else:
        print(f"No lectures on {args.day}.")


if __name__ == "__main__":
    main()
