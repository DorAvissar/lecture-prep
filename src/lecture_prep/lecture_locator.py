"""Find a lecture's files in Google Drive.

Each course folder has a "הרצאות" (lectures) sub-folder; anything else in the course folder, such as
tutorials, is ignored. Every file in the lectures folder starts with its lecture number, e.g.
"3.pdf" or "03 - Integrals.pdf", and all files with the same number belong to the same lecture.
Which number is taught today is decided elsewhere (see daily.py) - here we only find the files.
"""

import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Protocol

from lecture_prep.db.models import Course
from lecture_prep.google_api.drive import DriveItem

log = logging.getLogger(__name__)

LECTURE_NUMBER = re.compile(r"^\s*(\d+)")
PDF_MIME = "application/pdf"
LECTURES_SUBFOLDER = "הרצאות"


class Drive(Protocol):
    """The part of DriveClient the locator needs - tests pass a fake instead."""

    def list_folder(self, path: str) -> list[DriveItem]: ...


@dataclass(frozen=True)
class LectureMaterial:
    number: int
    files: tuple[DriveItem, ...]  # sorted by name


def lecture_number(filename: str) -> int | None:
    """The number at the start of a file name, or None when it has none."""
    match = LECTURE_NUMBER.match(filename)
    return int(match.group(1)) if match else None


def is_supported(item: DriveItem) -> bool:
    """Files the model can read: PDFs, and native Google docs (downloaded as PDF)."""
    return item.mime_type == PDF_MIME or item.is_google_doc


def group_by_lecture(items: list[DriveItem]) -> list[LectureMaterial]:
    """Group a course folder's files by lecture number, lowest number first."""
    groups: dict[int, list[DriveItem]] = defaultdict(list)
    for item in items:
        number = lecture_number(item.name)
        if item.is_folder or number is None:
            continue
        if not is_supported(item):
            log.warning("Skipping %s: only PDF files and Google docs are supported", item.path)
            continue
        groups[number].append(item)
    return [
        LectureMaterial(number=number, files=tuple(sorted(files, key=lambda item: item.name)))
        for number, files in sorted(groups.items())
    ]


def lectures_folder(course: Course) -> str:
    return f"{course.drive_folder.rstrip('/')}/{LECTURES_SUBFOLDER}"


def course_lectures(drive: Drive, course: Course) -> dict[int, LectureMaterial]:
    """All of a course's lectures found in Drive, by lecture number."""
    lectures = group_by_lecture(drive.list_folder(lectures_folder(course)))
    return {lecture.number: lecture for lecture in lectures}
