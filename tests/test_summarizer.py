"""Summarizer tests. A fake model records what it was asked and returns a canned reply."""

import pytest

from lecture_prep.db.models import SummaryKind
from lecture_prep.llm import LectureFile, Reply
from lecture_prep.summarizer import INSTRUCTIONS, SYSTEM_PROMPT, Summarizer

FILES = [LectureFile("03 - Integrals.pdf", b"%PDF-slides"), LectureFile("03 notes.pdf", b"%PDF-notes")]


class FakeModel:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def generate(self, system, files, turns, effort, max_tokens) -> Reply:
        self.calls.append({"system": system, "files": files, "turns": turns, "effort": effort})
        return Reply(text="סיכום", model="model-x")


def test_sends_the_files_and_the_instructions_for_the_kind():
    model = FakeModel()

    result = Summarizer(model).summarize(SummaryKind.PREP, "Calculus 2", FILES)

    [call] = model.calls
    assert call["system"] == SYSTEM_PROMPT
    assert call["files"] == FILES
    [turn] = call["turns"]
    assert turn.role == "user"
    assert "Calculus 2" in turn.content
    assert INSTRUCTIONS[SummaryKind.PREP] in turn.content
    assert call["effort"] == "high"
    assert (result.content, result.model) == ("סיכום", "model-x")


def test_recap_and_prep_use_different_instructions():
    model = FakeModel()

    Summarizer(model).summarize(SummaryKind.RECAP, "Calculus 2", FILES)

    text = model.calls[0]["turns"][0].content
    assert INSTRUCTIONS[SummaryKind.RECAP] in text
    assert INSTRUCTIONS[SummaryKind.PREP] not in text


def test_a_lecture_without_files_is_rejected():
    with pytest.raises(ValueError):
        Summarizer(FakeModel()).summarize(SummaryKind.PREP, "Calculus 2", [])
