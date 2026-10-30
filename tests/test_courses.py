from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from lecture_prep.courses import CourseEntry, load_courses, sync_courses
from lecture_prep.db.models import Course


def test_load_courses_reads_every_course_table():
    text = """
[[course]]
name = "Calculus 2"
aliases = ["חדוא"]
drive_folder = "Lectures/Calculus 2"

[[course]]
name = "Algorithms"
drive_folder = "Lectures/Algorithms"
"""
    assert load_courses(text) == [
        CourseEntry("Calculus 2", "Lectures/Calculus 2", ("חדוא",)),
        CourseEntry("Algorithms", "Lectures/Algorithms"),
    ]


def test_example_file_is_valid():
    assert load_courses(Path("courses.example.toml").read_text(encoding="utf-8"))


def test_sync_adds_new_courses_and_updates_existing_ones(db_session: Session):
    db_session.add(Course(name="Algorithms", aliases=["old"], drive_folder="Old/Algorithms"))
    db_session.commit()

    sync_courses(
        db_session,
        [
            CourseEntry("Algorithms", "Lectures/Algorithms", ("אלגו",)),
            CourseEntry("Calculus 2", "Lectures/Calculus 2"),
        ],
    )

    courses = {course.name: course for course in db_session.scalars(select(Course))}
    assert courses["Algorithms"].aliases == ["אלגו"]
    assert courses["Algorithms"].drive_folder == "Lectures/Algorithms"
    assert courses["Calculus 2"].aliases == []
