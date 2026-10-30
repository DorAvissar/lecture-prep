"""Send a day's morning message now, as a test, without recording it as sent:

    uv run python -m lecture_prep.send_test 2026-11-01

It prepares the day's summaries (stored, so the real morning reuses them) and sends the morning message
with its buttons, marked as a test. Nothing is recorded in sent_messages, so the real morning message
still goes out on the day. Point DATABASE_URL and PUBLIC_URL at the cloud to test the deployed app.
"""

import logging
import sys
from datetime import date
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from lecture_prep.config import get_settings
from lecture_prep.daily import Drive, Writer, prepare_day
from lecture_prep.db.session import SessionLocal
from lecture_prep.google_api.calendar import CalendarClient
from lecture_prep.google_api.drive import DriveClient
from lecture_prep.llm import make_model
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
    chat_id: int,
    day: date,
    tz: ZoneInfo,
    app_url: str | None,
) -> int:
    """Send `day`'s morning message now. Returns how many lectures it lists (0: nothing sent)."""
    briefs = prepare_day(session, calendar, drive, writer, day, tz)
    if not briefs:
        return 0
    text, buttons = morning_message(briefs, tz, app_url)
    messenger.send_message(chat_id, f"{TEST_MARK}\n\n{text}", buttons)
    return len(briefs)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    for noisy in ("httpx", "httpx2", "anthropic", "google_genai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    settings = get_settings()
    if settings.telegram_bot_token is None or settings.telegram_chat_id is None:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID first (see the README).")
    tz = ZoneInfo(settings.timezone)
    day = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()

    with (
        CalendarClient.from_settings(settings) as calendar,
        DriveClient.from_settings(settings) as drive,
        TelegramClient.from_token(settings.telegram_bot_token.get_secret_value()) as telegram,
        SessionLocal() as session,
    ):
        writer = Summarizer(make_model(settings))
        count = send_test(
            session,
            calendar,
            drive,
            writer,
            telegram,
            settings.telegram_chat_id,
            day,
            tz,
            settings.public_url,
        )
    print(f"Sent a test morning message with {count} lectures." if count else f"No lectures on {day}.")


if __name__ == "__main__":
    main()
