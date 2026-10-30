"""Summarizer tests. A fake Anthropic client records the request and returns a canned message."""

import base64
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from lecture_prep.db.models import SummaryKind
from lecture_prep.summarizer import INSTRUCTIONS, LectureFile, Summarizer, SummaryError

MODEL = "claude-opus-5-5"
FILES = [LectureFile("03 - Integrals.pdf", b"%PDF-slides"), LectureFile("03 notes.pdf", b"%PDF-notes")]


def message(*texts: str, stop_reason: str = "end_turn", model: str = MODEL) -> SimpleNamespace:
    blocks = [SimpleNamespace(type="thinking", thinking="")]
    blocks += [SimpleNamespace(type="text", text=text) for text in texts]
    return SimpleNamespace(content=blocks, stop_reason=stop_reason, stop_details=None, model=model)


class FakeClient:
    def __init__(self, reply: SimpleNamespace) -> None:
        self.requests: list[dict] = []

        @contextmanager
        def stream(**request):
            self.requests.append(request)
            yield SimpleNamespace(get_final_message=lambda: reply)

        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=stream))


def summarize(reply: SimpleNamespace, kind: SummaryKind = SummaryKind.PREP):
    client = FakeClient(reply)
    result = Summarizer(client, MODEL).summarize(kind, "Calculus 2", FILES)  # type: ignore[arg-type]
    return result, client.requests


def test_sends_every_pdf_then_the_instructions():
    _, [request] = summarize(message("סיכום"))

    [user] = request["messages"]
    *documents, instructions = user["content"]
    assert [doc["title"] for doc in documents] == ["03 - Integrals.pdf", "03 notes.pdf"]
    assert base64.b64decode(documents[0]["source"]["data"]) == b"%PDF-slides"
    assert documents[0]["source"]["media_type"] == "application/pdf"
    assert "Calculus 2" in instructions["text"]
    assert INSTRUCTIONS[SummaryKind.PREP] in instructions["text"]
    assert request["model"] == MODEL


def test_recap_and_prep_use_different_instructions():
    _, [recap] = summarize(message("x"), SummaryKind.RECAP)

    text = recap["messages"][0]["content"][-1]["text"]
    assert INSTRUCTIONS[SummaryKind.RECAP] in text
    assert INSTRUCTIONS[SummaryKind.PREP] not in text


def test_returns_the_text_and_the_model_that_wrote_it():
    result, _ = summarize(message("חלק א", "חלק ב", model="claude-opus-5"))

    assert result.content == "חלק אחלק ב"
    assert result.model == "claude-opus-5"


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
def test_unfinished_answers_raise(stop_reason):
    with pytest.raises(SummaryError):
        summarize(message("partial", stop_reason=stop_reason))


def test_empty_answer_raises():
    with pytest.raises(SummaryError):
        summarize(message("  "))


def test_a_lecture_without_files_is_rejected():
    with pytest.raises(ValueError):
        Summarizer(FakeClient(message("x")), MODEL).summarize(SummaryKind.PREP, "Calculus 2", [])  # type: ignore[arg-type]
