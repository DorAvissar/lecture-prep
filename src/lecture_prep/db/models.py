"""ORM models: a Course has many Lectures, a Lecture has a recap and a prep Summary."""

from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import ARRAY, BigInteger, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lecture_prep.db.base import Base


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    # Alternative names matched against calendar event titles, e.g. ["לינארית", "Linear Algebra"].
    aliases: Mapped[list[str]] = mapped_column(ARRAY(String(200)), default=list)
    drive_folder: Mapped[str] = mapped_column(
        String(500)
    )  # path in Google Drive, e.g. "Lectures/Linear Algebra"
    # Counting starts here: the first lecture the app handles. Later lectures follow the calendar.
    start_lecture: Mapped[int] = mapped_column(default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lectures: Mapped[list["Lecture"]] = relationship(
        back_populates="course", order_by="Lecture.number", cascade="all, delete-orphan"
    )


class Lecture(Base):
    __tablename__ = "lectures"
    __table_args__ = (UniqueConstraint("course_id", "number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    number: Mapped[int]  # order within the course: 1, 2, 3...
    title: Mapped[str | None] = mapped_column(String(300))  # name of the lecture's first file
    held_on: Mapped[date | None]  # the day it was taught; None until it shows up on the calendar
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    course: Mapped[Course] = relationship(back_populates="lectures")
    summaries: Mapped[list["Summary"]] = relationship(back_populates="lecture", cascade="all, delete-orphan")


class SummaryKind(StrEnum):
    RECAP = "recap"  # short reminder of a lecture that already happened
    PREP = "prep"  # intuition-first brief before the lecture


class Summary(Base):
    __tablename__ = "summaries"
    __table_args__ = (UniqueConstraint("lecture_id", "kind"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    lecture_id: Mapped[int] = mapped_column(ForeignKey("lectures.id", ondelete="CASCADE"), index=True)
    kind: Mapped[SummaryKind] = mapped_column(
        Enum(SummaryKind, name="summary_kind", values_callable=lambda kinds: [k.value for k in kinds])
    )
    content: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(100))  # which LLM produced it
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lecture: Mapped[Lecture] = relationship(back_populates="summaries")


class SentMessage(Base):
    """A Telegram message that was sent, so the scheduler never sends it twice."""

    __tablename__ = "sent_messages"
    __table_args__ = (UniqueConstraint("kind", "day", "event_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))  # "morning" or "reminder"
    day: Mapped[date]
    event_id: Mapped[str] = mapped_column(String(200), default="")  # the lecture's event; "" for morning
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Member(Base):
    """A classmate who joined through the invite link and gets the same messages as the owner."""

    __tablename__ = "members"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True)  # Telegram ids exceed 32 bits
    name: Mapped[str] = mapped_column(String(200), default="")
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChatUsage(Base):
    """How many chat questions a member asked on a day, for the daily limit."""

    __tablename__ = "chat_usage"
    __table_args__ = (UniqueConstraint("chat_id", "day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    day: Mapped[date]
    questions: Mapped[int] = mapped_column(default=0)
