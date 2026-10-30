"""Fakes shared by the pipeline and scheduler tests."""

from datetime import UTC, datetime

from lecture_prep.db.models import SummaryKind
from lecture_prep.google_api.drive import DriveItem
from lecture_prep.summarizer import LectureFile, SummaryResult


def pdf(name: str) -> DriveItem:
    return DriveItem(
        id=name,
        name=name,
        path=f"/Lectures/Calculus/הרצאות/{name}",
        mime_type="application/pdf",
        size=10,
        modified_at=datetime(2026, 10, 1, tzinfo=UTC),
    )


class FakeDrive:
    def __init__(self, *items: DriveItem) -> None:
        self.items = list(items)
        self.downloaded: list[str] = []

    def list_folder(self, path: str) -> list[DriveItem]:
        assert path == "Lectures/Calculus/הרצאות"
        return self.items

    def download(self, item: DriveItem) -> bytes:
        self.downloaded.append(item.name)
        return f"%PDF {item.name}".encode()


class FakeWriter:
    def __init__(self) -> None:
        self.calls: list[tuple[SummaryKind, list[str]]] = []

    def summarize(self, kind: SummaryKind, course_name: str, files: list[LectureFile]) -> SummaryResult:
        self.calls.append((kind, [file.name for file in files]))
        return SummaryResult(content=f"{kind} of {files[0].name}", model="fake-model")
