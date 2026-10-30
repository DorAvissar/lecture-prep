"""Find a course's current and previous lecture files in Google Drive.

Naming convention: every file in a course folder starts with its lecture number, e.g.
"03 - Integrals.pdf" or "3 summary.pdf". All files with the same number belong to the same lecture.
The highest number is today's lecture; the next one down is the previous lecture.
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


class Drive(Protocol):
    """The part of DriveClient the locator needs - tests pass a fake instead."""

    def list_folder(self, path: str) -> list[DriveItem]: ...


@dataclass(frozen=True)
class LectureMaterial:
    number: int
    files: tuple[DriveItem, ...]  # sorted by name


@dataclass(frozen=True)
class CourseMaterial:
    current: LectureMaterial | None  # None when the folder has no numbered files yet
    previous: LectureMaterial | None  # None when the course has only one lecture so far


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


def locate(drive: Drive, course: Course) -> CourseMaterial:
    """Return the current and previous lecture of `course`, read from its Drive folder."""
    lectures = group_by_lecture(drive.list_folder(course.drive_folder))
    return CourseMaterial(
        current=lectures[-1] if lectures else None,
        previous=lectures[-2] if len(lectures) >= 2 else None,
    )
