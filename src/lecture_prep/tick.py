"""One scheduler tick. Run it every 10-15 minutes - from the command line, or in the cloud by calling
POST /internal/tick (see web/internal.py):

    uv run python -m lecture_prep.tick

From the morning hour on, it prepares the day's summaries, sends the morning message once, and sends
each lecture's reminder once when the lecture is close. Everything it sent is recorded, so extra or
repeated ticks are harmless, and a tick that failed (for example, the Claude API was down) is simply
retried by the next one.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from lecture_prep.config import Settings, get_settings
from lecture_prep.daily import Drive, Writer, prepare_day
from lecture_prep.db.models import SentMessage
from lecture_prep.db.session import SessionLocal
from lecture_prep.google_api.calendar import CalendarClient
from lecture_prep.google_api.drive import DriveClient
from lecture_prep.llm import make_model
from lecture_prep.members import process_joins, recipients
from lecture_prep.summarizer import Summarizer
from lecture_prep.telegram.client import Button, TelegramClient, TelegramError
from lecture_prep.telegram.messages import morning_message, reminder_message

log = logging.getLogger(__name__)

MORNING = "morning"
REMINDER = "reminder"


class Messenger(Protocol):
    def send_message(self, chat_id: int, html: str, buttons: list[Button] | None = None) -> None: ...


@dataclass(frozen=True)
class Schedule:
    tz: ZoneInfo
    morning_hour: int
    reminder_minutes: int
    app_url: str | None = None  # where the Mini App is served; None: messages go without buttons


def tick(
    session: Session,
    calendar: CalendarClient,
    drive: Drive,
    writer: Writer,
    messenger: Messenger,
    chat_id: int,
    schedule: Schedule,
    now: datetime,
) -> list[str]:
    """Send whatever is due at `now`. Returns a description of each message sent."""
    local_now = now.astimezone(schedule.tz)
    day = local_now.date()
    if local_now.hour < schedule.morning_hour:
        return []
    briefs = prepare_day(session, calendar, drive, writer, day, schedule.tz)
    sent: list[str] = []

    if briefs and not was_sent(session, MORNING, day):
        text, buttons = morning_message(briefs, schedule.tz, schedule.app_url)
        send_to_all(session, messenger, chat_id, text, buttons)
        mark_sent(session, MORNING, day)
        sent.append(MORNING)

    lead = timedelta(minutes=schedule.reminder_minutes)
    for brief in briefs:
        due = brief.event.start - lead <= now < brief.event.start
        if due and not was_sent(session, REMINDER, day, brief.event.id):
            text, buttons = reminder_message(brief, schedule.tz, schedule.app_url)
            send_to_all(session, messenger, chat_id, text, buttons)
            mark_sent(session, REMINDER, day, brief.event.id)
            sent.append(f"{REMINDER} {brief.course.name}")
    return sent


def send_to_all(
    session: Session, messenger: Messenger, owner_chat_id: int, text: str, buttons: list[Button]
) -> None:
    """Send to the owner and every member. One member who blocked the bot does not stop the rest."""
    for chat_id in recipients(session, owner_chat_id):
        try:
            messenger.send_message(chat_id, text, buttons)
        except TelegramError as error:
            if chat_id == owner_chat_id:
                raise
            log.warning("Could not send to member %s: %s", chat_id, error)


def was_sent(session: Session, kind: str, day: date, event_id: str = "") -> bool:
    query = select(SentMessage.id).where(
        SentMessage.kind == kind, SentMessage.day == day, SentMessage.event_id == event_id
    )
    return session.scalar(query) is not None


def mark_sent(session: Session, kind: str, day: date, event_id: str = "") -> None:
    session.add(SentMessage(kind=kind, day=day, event_id=event_id))
    session.commit()


class NotConfigured(RuntimeError):
    """Telegram is not set up yet."""


def run_once(settings: Settings) -> list[str]:
    """One tick with the real calendar, Drive, model and Telegram. Returns what was sent."""
    if settings.telegram_bot_token is None or settings.telegram_chat_id is None:
        raise NotConfigured("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID first (see the README).")
    schedule = Schedule(
        ZoneInfo(settings.timezone), settings.morning_hour, settings.reminder_minutes, settings.public_url
    )
    with (
        CalendarClient.from_settings(settings) as calendar,
        DriveClient.from_settings(settings) as drive,
        TelegramClient.from_token(settings.telegram_bot_token.get_secret_value()) as telegram,
        SessionLocal() as session,
    ):
        invite_code = settings.invite_code.get_secret_value() if settings.invite_code else None
        process_joins(session, telegram, invite_code, settings.telegram_chat_id)
        writer = Summarizer(make_model(settings))
        now = datetime.now().astimezone()
        sent = tick(session, calendar, drive, writer, telegram, settings.telegram_chat_id, schedule, now)
    log.info("Sent: %s", ", ".join(sent) or "nothing")
    return sent


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        run_once(get_settings())
    except NotConfigured as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()
