"""Lecture locator tests. A fake Drive returns fixed folder listings - no network needed."""

import logging
from datetime import UTC, datetime

from lecture_prep.db.models import Course
from lecture_prep.google_api.drive import FOLDER_MIME, DriveItem, FolderNotFoundError
from lecture_prep.lecture_locator import LectureMaterial, course_lectures, group_by_lecture, lecture_number

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


def test_lecture_number_follows_the_word_lecture():
    # The course name has its own number ("2"); the lecture number is the one after "הרצאה".
    assert lecture_number("חדו״א 2- הרצאה 13 לנדסמן .pdf") == 13
    assert lecture_number("תכנות מערכות- הרצאה 7 מני.pdf") == 7
    assert lecture_number("הרצאה7.pdf") == 7


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


def test_course_lectures_reads_the_lectures_subfolder_by_number():
    one, two_slides, two_notes = item("1.pdf"), item("2.pdf"), item("2 notes.pdf")
    drive = FakeDrive([two_slides, one, two_notes])

    lectures = course_lectures(drive, CALCULUS)

    assert lectures == {
        1: LectureMaterial(1, (one,)),
        2: LectureMaterial(2, (two_notes, two_slides)),
    }
    assert drive.asked == ["Lectures/Calculus 2/הרצאות"]


def test_course_lectures_of_an_empty_folder():
    assert course_lectures(FakeDrive([]), CALCULUS) == {}


def test_course_lectures_without_a_lectures_folder(caplog):
    class NoFolderDrive:
        def list_folder(self, path: str) -> list[DriveItem]:
            raise FolderNotFoundError(path)

    with caplog.at_level(logging.WARNING):
        assert course_lectures(NoFolderDrive(), CALCULUS) == {}
    assert "No lectures folder" in caplog.text
