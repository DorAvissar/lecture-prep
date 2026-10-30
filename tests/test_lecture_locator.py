"""Lecture locator tests. A fake Drive returns fixed folder listings - no network needed."""

import logging
from datetime import UTC, datetime

from lecture_prep.db.models import Course
from lecture_prep.google_api.drive import FOLDER_MIME, DriveItem
from lecture_prep.lecture_locator import (
    CourseMaterial,
    LectureMaterial,
    group_by_lecture,
    lecture_number,
    locate,
)

PDF = "application/pdf"
CALCULUS = Course(name="חדוא 2", aliases=[], drive_folder="Lectures/Calculus 2")


def item(name: str, mime_type: str = PDF) -> DriveItem:
    return DriveItem(
        id=name,
        name=name,
        path=f"/Lectures/Calculus 2/{name}",
        mime_type=mime_type,
        size=100,
        modified_at=datetime(2026, 10, 20, tzinfo=UTC),
    )


class FakeDrive:
    def __init__(self, items: list[DriveItem]) -> None:
        self.items = items
        self.asked: list[str] = []

    def list_folder(self, path: str) -> list[DriveItem]:
        self.asked.append(path)
        return self.items


def test_lecture_number_reads_leading_digits():
    assert lecture_number("03 - Integrals.pdf") == 3
    assert lecture_number("12 summary.pdf") == 12
    assert lecture_number("  7.pdf") == 7


def test_lecture_number_is_none_without_a_leading_number():
    assert lecture_number("syllabus.pdf") is None
    assert lecture_number("Lecture 3.pdf") is None


def test_files_with_the_same_number_belong_to_one_lecture():
    slides, notes = item("02 - Derivatives.pdf"), item("02 - Notes.pdf")

    [lecture] = group_by_lecture([notes, slides])

    assert lecture == LectureMaterial(number=2, files=(slides, notes))  # sorted by name


def test_lectures_are_ordered_by_number_not_by_name():
    nine, ten = item("9.pdf"), item("10.pdf")

    assert [lecture.number for lecture in group_by_lecture([ten, nine])] == [9, 10]


def test_skips_folders_unnumbered_and_unsupported_files(caplog):
    google_slides = item("04 - Series", "application/vnd.google-apps.presentation")
    files = [
        item("05 old", FOLDER_MIME),
        item("syllabus.pdf"),
        item("04 - Series.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
        google_slides,
    ]

    with caplog.at_level(logging.WARNING):
        lectures = group_by_lecture(files)

    assert lectures == [LectureMaterial(number=4, files=(google_slides,))]
    assert "04 - Series.pptx" in caplog.text


def test_locate_returns_highest_as_current_and_next_highest_as_previous():
    one, two, three = item("01.pdf"), item("02.pdf"), item("03.pdf")
    drive = FakeDrive([three, one, two])

    material = locate(drive, CALCULUS)

    assert material == CourseMaterial(
        current=LectureMaterial(3, (three,)), previous=LectureMaterial(2, (two,))
    )
    assert drive.asked == ["Lectures/Calculus 2"]


def test_previous_skips_gaps_in_numbering():
    material = locate(FakeDrive([item("01.pdf"), item("04.pdf")]), CALCULUS)

    assert material.previous is not None
    assert material.previous.number == 1


def test_first_lecture_has_no_previous():
    material = locate(FakeDrive([item("01.pdf")]), CALCULUS)

    assert material.current == LectureMaterial(1, (item("01.pdf"),))
    assert material.previous is None


def test_empty_folder():
    assert locate(FakeDrive([]), CALCULUS) == CourseMaterial(current=None, previous=None)
