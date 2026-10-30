"""Keep the courses table in step with a small TOML file you edit by hand.

    uv run python -m lecture_prep.courses            # reads courses.toml

Courses are matched by name: new ones are added, existing ones get their aliases and folder updated.
Courses missing from the file are left alone - deleting one would delete its stored summaries too.
"""

import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from lecture_prep.db.models import Course
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


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_FILE
    entries = load_courses(path.read_text(encoding="utf-8"))
    with SessionLocal() as session:
        sync_courses(session, entries)
    for entry in entries:
        print(f"{entry.name}  ->  {entry.drive_folder}")


if __name__ == "__main__":
    main()
