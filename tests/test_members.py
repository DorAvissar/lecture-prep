"""Classmates joining through the invite link, and their daily chat limit."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from lecture_prep.db.models import Member
from lecture_prep.members import (
    NEED_INVITE,
    WELCOME,
    invite_link,
    process_joins,
    recipients,
    use_question,
)

OWNER = 1000
CODE = "abc123"


class FakeBot:
    def __init__(self, *messages: tuple[int, str, str]) -> None:
        self.pending = [
            {"update_id": 500 + i, "message": {"chat": {"id": chat_id, "first_name": name}, "text": text}}
            for i, (chat_id, name, text) in enumerate(messages)
        ]
        self.confirmed: list[int] = []
        self.sent: list[tuple[int, str]] = []

    def updates(self, offset=None):
        if offset is not None:
            self.confirmed.append(offset)
            return []
        return self.pending

    def send_message(self, chat_id, html, buttons=None):
        self.sent.append((chat_id, html))


def names(session: Session) -> list[str]:
    return [member.name for member in session.scalars(select(Member).order_by(Member.id))]


def test_the_right_code_joins_and_gets_a_welcome(db_session):
    bot = FakeBot((7, "Noa", f"/start {CODE}"))

    assert process_joins(db_session, bot, CODE, OWNER) == ["Noa"]

    assert names(db_session) == ["Noa"]
    assert bot.sent == [(7, WELCOME)]
    assert bot.confirmed == [501]  # read messages are confirmed so they are not read again


def test_a_wrong_or_missing_code_does_not_join(db_session):
    bot = FakeBot((7, "Noa", "/start wrong"), (8, "Avi", "/start"))

    assert process_joins(db_session, bot, CODE, OWNER) == []

    assert names(db_session) == []
    assert bot.sent == [(7, NEED_INVITE), (8, NEED_INVITE)]


def test_without_an_invite_code_nobody_can_join(db_session):
    bot = FakeBot((7, "Noa", f"/start {CODE}"))

    assert process_joins(db_session, bot, None, OWNER) == []
    assert names(db_session) == []


def test_owner_and_existing_members_and_other_messages_are_left_alone(db_session):
    db_session.add(Member(chat_id=7, name="Noa"))
    db_session.commit()
    bot = FakeBot((OWNER, "Dor", f"/start {CODE}"), (7, "Noa", f"/start {CODE}"), (9, "Tal", "hello"))

    assert process_joins(db_session, bot, CODE, OWNER) == []

    assert names(db_session) == ["Noa"]
    assert bot.sent == []


def test_recipients_are_the_owner_then_members(db_session):
    db_session.add_all([Member(chat_id=7, name="Noa"), Member(chat_id=8, name="Avi")])
    db_session.commit()

    assert recipients(db_session, OWNER) == [OWNER, 7, 8]


def test_daily_question_limit(db_session):
    day = date(2026, 11, 1)

    assert [use_question(db_session, 7, day, limit=2) for _ in range(3)] == [True, True, False]
    assert use_question(db_session, 7, date(2026, 11, 2), limit=2)  # a new day starts over
    assert use_question(db_session, 8, day, limit=2)  # counted per person


def test_invite_link():
    assert invite_link("lecture_prep_bot", CODE) == "https://t.me/lecture_prep_bot?start=abc123"
