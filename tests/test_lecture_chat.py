"""Lecture chat tests with a fake model."""

import pytest

from lecture_prep.lecture_chat import CHAT_SYSTEM_PROMPT, LectureChat
from lecture_prep.llm import ChatMessage, LectureFile, Reply

CURRENT = [LectureFile("הרצאה 5.pdf", b"%PDF-5")]
PREVIOUS = [LectureFile("הרצאה 4.pdf", b"%PDF-4")]


class FakeModel:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def generate(self, system, files, turns, effort, max_tokens) -> Reply:
        self.calls.append({"system": system, "files": files, "turns": turns, "effort": effort})
        return Reply(text="תשובה", model="m")


def ask(model: FakeModel, *history: ChatMessage, previous=PREVIOUS) -> str:
    return LectureChat(model).answer("Systems", 5, CURRENT, previous, list(history))


def test_files_of_both_lectures_go_with_the_first_question():
    model = FakeModel()

    assert ask(model, ChatMessage("user", "מה זה מצביע?")) == "תשובה"

    [call] = model.calls
    assert call["system"] == CHAT_SYSTEM_PROMPT
    assert [file.name for file in call["files"]] == ["הרצאה 4.pdf", "הרצאה 5.pdf"]
    [first] = call["turns"]
    assert "lecture 5" in first.content and "lecture 4" in first.content
    assert first.content.endswith("מה זה מצביע?")


def test_follow_ups_keep_the_conversation():
    model = FakeModel()

    ask(
        model,
        ChatMessage("user", "שאלה 1"),
        ChatMessage("assistant", "תשובה 1"),
        ChatMessage("user", "שאלה 2"),
    )

    turns = model.calls[0]["turns"]
    assert [turn.role for turn in turns] == ["user", "assistant", "user"]
    assert turns[1:] == [ChatMessage("assistant", "תשובה 1"), ChatMessage("user", "שאלה 2")]


def test_first_lecture_has_no_previous_files():
    model = FakeModel()

    ask(model, ChatMessage("user", "?"), previous=[])

    assert len(model.calls[0]["files"]) == 1
    assert "lecture 4" not in model.calls[0]["turns"][0].content


def test_conversation_must_end_with_a_question():
    with pytest.raises(ValueError):
        ask(FakeModel(), ChatMessage("user", "q"), ChatMessage("assistant", "a"))
