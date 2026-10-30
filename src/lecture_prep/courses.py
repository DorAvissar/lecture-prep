"""Keep the courses table in step with a small TOML file you edit by hand, and set lecture numbers.

    uv run python -m lecture_prep.courses                       # load courses.toml
    uv run python -m lecture_prep.courses next "חדוא 2" 5       # the next lecture of a course is 5

Courses are matched by name: new ones are added, existing ones get their aliases and folder updated.
Courses missing from the file are left alone - deleting one would delete its stored summaries too.
"""

import argparse
import tomllib
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from lecture_prep.db.models import Course, Lecture
from lecture_prep.db.session import SessionLocal

DEFAULT_FILE = Path("courses.toml")


@dataclass(frozen=True)
class CourseEntry:
    name: str
    drive_folder: str
    aliases: tuple[str, ...] = ()


def load_courses(text: str) -> list[CourseEntry]:
    """Parse the [[course]] tables of a courses.toml file."""
    return [
        CourseEntry(
            name=raw["name"],
            drive_folder=raw["drive_folder"],
            aliases=tuple(raw.get("aliases", [])),
        )
        for raw in tomllib.loads(text).get("course", [])
    ]


def sync_courses(session: Session, entries: list[CourseEntry]) -> None:
    existing = {course.name: course for course in session.scalars(select(Course))}
    for entry in entries:
        course = existing.get(entry.name)
        if course is None:
            course = Course(name=entry.name)
            session.add(course)
        course.drive_folder = entry.drive_folder
        course.aliases = list(entry.aliases)
    session.commit()


def set_next_lecture(session: Session, course_name: str, number: int) -> Course:
    """Make `number` the course's next lecture - at setup, or after a cancelled lecture moved the count.

    Lectures from `number` on are no longer marked as taught; their stored summaries are kept.
    """
    course = session.scalars(select(Course).where(Course.name == course_name)).one_or_none()
    if course is None:
        raise LookupError(f"no course named {course_name!r}")
    course.start_lecture = number
    for lecture in session.scalars(
        select(Lecture).where(Lecture.course_id == course.id, Lecture.number >= number)
    ):
        lecture.held_on = None
    session.commit()
    return course


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m lecture_prep.courses")
    commands = parser.add_subparsers(dest="command")
    load = commands.add_parser("load", help="load courses.toml (the default)")
    load.add_argument("file", nargs="?", type=Path, default=DEFAULT_FILE)
    next_ = commands.add_parser("next", help="set the number of a course's next lecture")
    next_.add_argument("course")
    next_.add_argument("number", type=int)
    args = parser.parse_args()

    with SessionLocal() as session:
        if args.command == "next":
            course = set_next_lecture(session, args.course, args.number)
            print(f"{course.name}: next lecture is {args.number}")
            return
        entries = load_courses(getattr(args, "file", DEFAULT_FILE).read_text(encoding="utf-8"))
        sync_courses(session, entries)
    for entry in entries:
        print(f"{entry.name}  ->  {entry.drive_folder}")


if __name__ == "__main__":
    main()
