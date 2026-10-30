from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from lecture_prep.courses import CourseEntry, load_courses, set_next_lecture, sync_courses
from lecture_prep.db.models import Course, Lecture


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


def test_set_next_lecture_rewinds_the_count(db_session: Session):
    course = Course(name="Calculus 2", drive_folder="Lectures/Calculus 2")
    course.lectures = [
        Lecture(number=1, held_on=date(2026, 11, 2)),
        Lecture(number=2, held_on=date(2026, 11, 9)),  # cancelled, but it was on the calendar
    ]
    db_session.add(course)
    db_session.commit()

    set_next_lecture(db_session, "Calculus 2", 2)

    assert course.start_lecture == 2
    assert [lecture.held_on for lecture in course.lectures] == [date(2026, 11, 2), None]


def test_set_next_lecture_of_an_unknown_course(db_session: Session):
    with pytest.raises(LookupError):
        set_next_lecture(db_session, "Nope", 3)
