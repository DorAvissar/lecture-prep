"""ORM models: a Course has many Lectures, a Lecture has a recap and a prep Summary."""

from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import ARRAY, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, func
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
    title: Mapped[str | None] = mapped_column(String(300))
    source_path: Mapped[str] = mapped_column(String(1000))  # file path inside Google Drive
    held_on: Mapped[date | None]
    extracted_text: Mapped[str | None] = mapped_column(Text)
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
