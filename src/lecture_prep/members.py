"""Sharing the bot with classmates who take the same courses.

A classmate joins by opening the invite link, https://t.me/<bot>?start=<INVITE_CODE>, which sends the bot
"/start <INVITE_CODE>". Each scheduler tick reads new messages and adds whoever sent the right code. Members
get the same morning messages and reminders as the owner, and can use the Mini App with a daily limit on
chat questions.

    uv run python -m lecture_prep.members invite        # print the invite link
    uv run python -m lecture_prep.members list          # who joined
    uv run python -m lecture_prep.members remove <id>   # remove a member
"""

import argparse
import hmac
import logging
from datetime import date
from typing import Any, Protocol

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from lecture_prep.config import Settings, get_settings
from lecture_prep.db.models import ChatUsage, Member
from lecture_prep.db.session import SessionLocal
from lecture_prep.telegram.client import Button, TelegramClient

log = logging.getLogger(__name__)

WELCOME = (
    "👋 <b>ברוך הבא!</b>\n"
    "מעכשיו תקבל כל בוקר את ההרצאות של היום, עם הכנה, חזרה וצ'אט לשאלות, ותזכורת לפני כל הרצאה."
)
NEED_INVITE = "הבוט הזה פרטי. כדי להצטרף צריך קישור הזמנה."


class Bot(Protocol):
    def updates(self, offset: int | None = None) -> list[dict[str, Any]]: ...
    def send_message(self, chat_id: int, html: str, buttons: list[Button] | None = None) -> None: ...


def recipients(session: Session, owner_chat_id: int) -> list[int]:
    """Everyone who gets the messages: the owner first, then members in the order they joined."""
    members = session.scalars(select(Member.chat_id).order_by(Member.joined_at, Member.id))
    return [owner_chat_id, *(chat_id for chat_id in members if chat_id != owner_chat_id)]


def is_member(session: Session, chat_id: int) -> bool:
    return session.scalar(select(Member.id).where(Member.chat_id == chat_id)) is not None


def process_joins(session: Session, bot: Bot, invite_code: str | None, owner_chat_id: int) -> list[str]:
    """Read new messages to the bot; add whoever sent "/start <invite code>". Returns the names added."""
    updates = bot.updates()
    joined: list[str] = []
    for update in updates:
        message = update.get("message") or {}
        chat = message.get("chat") or {}
        chat_id, text = chat.get("id"), (message.get("text") or "").strip()
        if chat_id is None or chat_id == owner_chat_id or not text.startswith("/start"):
            continue
        if is_member(session, chat_id):
            continue
        code = text.removeprefix("/start").strip()
        if invite_code and code and hmac.compare_digest(code, invite_code):
            name = chat.get("first_name") or chat.get("username") or ""
            session.add(Member(chat_id=chat_id, name=name))
            session.commit()
            bot.send_message(chat_id, WELCOME)
            joined.append(name)
            log.info("New member: %s (%s)", name, chat_id)
        else:
            bot.send_message(chat_id, NEED_INVITE)
    if updates:
        bot.updates(offset=updates[-1]["update_id"] + 1)  # confirm, so they are not read again
    return joined


def use_question(session: Session, chat_id: int, day: date, limit: int) -> bool:
    """Count one chat question for `chat_id` on `day`; False (and nothing counted) when over the limit."""
    usage = session.scalar(select(ChatUsage).where(ChatUsage.chat_id == chat_id, ChatUsage.day == day))
    if usage is None:
        usage = ChatUsage(chat_id=chat_id, day=day, questions=0)
        session.add(usage)
    if usage.questions >= limit:
        return False
    usage.questions += 1
    session.commit()
    return True


def invite_link(bot_username: str, invite_code: str) -> str:
    return f"https://t.me/{bot_username}?start={invite_code}"


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m lecture_prep.members")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("invite", help="print the invite link")
    commands.add_parser("list", help="list members")
    remove = commands.add_parser("remove", help="remove a member by chat id")
    remove.add_argument("chat_id", type=int)
    args = parser.parse_args()
    settings: Settings = get_settings()

    if args.command == "invite":
        if settings.telegram_bot_token is None or settings.invite_code is None:
            raise SystemExit("Set TELEGRAM_BOT_TOKEN and INVITE_CODE first.")
        with TelegramClient.from_token(settings.telegram_bot_token.get_secret_value()) as telegram:
            print(invite_link(telegram.bot_username(), settings.invite_code.get_secret_value()))
        return
    with SessionLocal() as session:
        if args.command == "list":
            for member in session.scalars(select(Member).order_by(Member.joined_at)):
                print(f"{member.chat_id}  {member.name}  (joined {member.joined_at:%Y-%m-%d})")
        else:
            removed = session.execute(delete(Member).where(Member.chat_id == args.chat_id)).rowcount
            session.commit()
            print("Removed." if removed else "No member with that chat id.")


if __name__ == "__main__":
    main()
