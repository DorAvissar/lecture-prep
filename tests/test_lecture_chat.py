"""Lecture chat tests with a fake Anthropic client."""

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from lecture_prep.lecture_chat import ChatMessage, LectureChat
from lecture_prep.summarizer import LectureFile, SummaryError

CURRENT = [LectureFile("הרצאה 5.pdf", b"%PDF-5")]
PREVIOUS = [LectureFile("הרצאה 4.pdf", b"%PDF-4")]


class FakeClient:
    def __init__(self, text: str = "תשובה", stop_reason: str = "end_turn") -> None:
        self.requests: list[dict] = []
        usage = SimpleNamespace(input_tokens=100, cache_read_input_tokens=9000, output_tokens=50)
        reply = SimpleNamespace(
            content=[SimpleNamespace(type="text", text=text)], stop_reason=stop_reason, usage=usage
        )

        @contextmanager
        def stream(**request):
            self.requests.append(request)
            yield SimpleNamespace(get_final_message=lambda: reply)

        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=stream))


def ask(client: FakeClient, *history: ChatMessage, previous=PREVIOUS) -> str:
    return LectureChat(client, "claude-opus-5-5").answer("Systems", 5, CURRENT, previous, list(history))  # type: ignore[arg-type]


def test_first_question_comes_after_both_lectures_files():
    client = FakeClient()

    assert ask(client, ChatMessage("user", "מה זה מצביע?")) == "תשובה"

    [user] = client.requests[0]["messages"]
    *documents, intro, question = user["content"]
    assert [doc["title"] for doc in documents] == ["הרצאה 4.pdf", "הרצאה 5.pdf"]
    assert documents[-1]["cache_control"] == {"type": "ephemeral"}
    assert "lecture 5" in intro["text"] and "lecture 4" in intro["text"]
    assert question["text"] == "מה זה מצביע?"


def test_follow_ups_keep_the_conversation():
    client = FakeClient()

    ask(
        client,
        ChatMessage("user", "שאלה 1"),
        ChatMessage("assistant", "תשובה 1"),
        ChatMessage("user", "שאלה 2"),
    )

    messages = client.requests[0]["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant", "user"]
    assert messages[1:] == [
        {"role": "assistant", "content": "תשובה 1"},
        {"role": "user", "content": "שאלה 2"},
    ]


def test_first_lecture_has_no_previous_files():
    client = FakeClient()

    ask(client, ChatMessage("user", "?"), previous=[])

    *documents, intro, _ = client.requests[0]["messages"][0]["content"]
    assert len(documents) == 1
    assert "lecture 4" not in intro["text"]


def test_conversation_must_end_with_a_question():
    with pytest.raises(ValueError):
        ask(FakeClient(), ChatMessage("user", "q"), ChatMessage("assistant", "a"))


def test_refusal_raises():
    with pytest.raises(SummaryError):
        ask(FakeClient(stop_reason="refusal"), ChatMessage("user", "?"))
