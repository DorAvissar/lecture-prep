"""Provider tests: Claude and Gemini behind the same Model interface, with fake SDK clients."""

import base64
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from google.genai import errors as genai_errors

from lecture_prep.llm import (
    ChatMessage,
    ClaudeModel,
    FallbackModel,
    GeminiModel,
    LectureFile,
    ModelError,
    Reply,
)

FILES = [LectureFile("4.pdf", b"%PDF-4"), LectureFile("5.pdf", b"%PDF-5")]
TURNS = [ChatMessage("user", "שאלה 1"), ChatMessage("assistant", "תשובה 1"), ChatMessage("user", "שאלה 2")]


# --- Claude -----------------------------------------------------------------------------------------


class FakeAnthropic:
    def __init__(self, *texts: str, stop_reason: str = "end_turn", model: str = "claude-opus-5-5") -> None:
        self.requests: list[dict] = []
        usage = SimpleNamespace(
            input_tokens=100, cache_creation_input_tokens=0, cache_read_input_tokens=0, output_tokens=50
        )
        blocks = [SimpleNamespace(type="thinking", thinking="")]
        blocks += [SimpleNamespace(type="text", text=text) for text in texts]
        reply = SimpleNamespace(
            content=blocks, stop_reason=stop_reason, stop_details=None, model=model, usage=usage
        )

        @contextmanager
        def stream(**request):
            self.requests.append(request)
            yield SimpleNamespace(get_final_message=lambda: reply)

        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=stream))


def claude(client: FakeAnthropic, turns=TURNS):
    return ClaudeModel(client, "claude-opus-5-5").generate("sys", FILES, turns, "high", 1000)  # type: ignore[arg-type]


def test_claude_puts_cached_pdfs_before_the_first_question():
    client = FakeAnthropic("תשובה")

    reply = claude(client)

    [request] = client.requests
    assert request["system"] == "sys"
    assert request["output_config"] == {"effort": "high"}
    first, *rest = request["messages"]
    *documents, question = first["content"]
    assert [doc["title"] for doc in documents] == ["4.pdf", "5.pdf"]
    assert base64.b64decode(documents[0]["source"]["data"]) == b"%PDF-4"
    assert "cache_control" not in documents[0]
    assert documents[-1]["cache_control"] == {"type": "ephemeral"}
    assert question == {"type": "text", "text": "שאלה 1"}
    assert rest == [{"role": "assistant", "content": "תשובה 1"}, {"role": "user", "content": "שאלה 2"}]
    assert (reply.text, reply.model) == ("תשובה", "claude-opus-5-5")


def test_claude_joins_text_blocks_and_reports_the_fallback_model():
    reply = claude(FakeAnthropic("חלק א", "חלק ב", model="claude-opus-5"))

    assert (reply.text, reply.model) == ("חלק אחלק ב", "claude-opus-5")


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
def test_claude_unfinished_answers_raise(stop_reason):
    with pytest.raises(ModelError):
        claude(FakeAnthropic("partial", stop_reason=stop_reason))


def test_claude_empty_answer_raises():
    with pytest.raises(ModelError):
        claude(FakeAnthropic("  "))


# --- Gemini -----------------------------------------------------------------------------------------


class FakeGenai:
    def __init__(self, text: str | None = "תשובה", finish_reason: str = "STOP") -> None:
        self.requests: list[dict] = []
        usage = SimpleNamespace(
            prompt_token_count=100,
            cached_content_token_count=0,
            candidates_token_count=50,
            thoughts_token_count=10,
        )
        candidate = SimpleNamespace(finish_reason=SimpleNamespace(name=finish_reason))
        response = SimpleNamespace(text=text, usage_metadata=usage, candidates=[candidate])

        def generate_content(**request):
            self.requests.append(request)
            return response

        self.models = SimpleNamespace(generate_content=generate_content)


def gemini(client: FakeGenai):
    return GeminiModel(client, "gemini-x").generate("sys", FILES, TURNS, "medium", 1000)  # type: ignore[arg-type]


def test_gemini_sends_pdfs_then_the_conversation():
    client = FakeGenai()

    reply = gemini(client)

    [request] = client.requests
    assert request["model"] == "gemini-x"
    config = request["config"]
    assert config.system_instruction == "sys"
    assert config.max_output_tokens == 1000
    assert config.thinking_config.thinking_level.name == "MEDIUM"
    first, answer, follow_up = request["contents"]
    assert first.role == "user"
    *pdfs, question = first.parts
    assert [part.inline_data.data for part in pdfs] == [b"%PDF-4", b"%PDF-5"]
    assert {part.inline_data.mime_type for part in pdfs} == {"application/pdf"}
    assert question.text == "שאלה 1"
    assert (answer.role, answer.parts[0].text) == ("model", "תשובה 1")
    assert (follow_up.role, follow_up.parts[0].text) == ("user", "שאלה 2")
    assert (reply.text, reply.model) == ("תשובה", "gemini-x")


@pytest.mark.parametrize("finish_reason", ["SAFETY", "MAX_TOKENS"])
def test_gemini_unfinished_answers_raise(finish_reason):
    with pytest.raises(ModelError):
        gemini(FakeGenai(finish_reason=finish_reason))


def test_gemini_empty_answer_raises():
    with pytest.raises(ModelError):
        gemini(FakeGenai(text=None))


# --- Backup model -----------------------------------------------------------------------------------


class StubModel:
    def __init__(self, name: str, fails: bool = False) -> None:
        self.name, self.fails, self.calls = name, fails, 0

    def generate(self, system, files, turns, effort, max_tokens):
        self.calls += 1
        if self.fails:
            raise ModelError(f"{self.name} is over its usage limit")
        return Reply(text=f"from {self.name}", model=self.name)


def test_backup_is_not_used_while_the_main_model_works():
    main, backup = StubModel("gemini"), StubModel("sonnet")

    reply = FallbackModel(main, backup).generate("sys", FILES, TURNS, "high", 1000)

    assert reply.model == "gemini"
    assert backup.calls == 0


def test_backup_answers_when_the_main_model_fails(caplog):
    main, backup = StubModel("gemini", fails=True), StubModel("sonnet")

    reply = FallbackModel(main, backup).generate("sys", FILES, TURNS, "high", 1000)

    assert (reply.text, reply.model) == ("from sonnet", "sonnet")
    assert "usage limit" in caplog.text


def test_gemini_api_errors_become_model_errors():
    client = FakeGenai()

    def over_limit(**request):
        raise genai_errors.ClientError(429, {"error": {"message": "quota", "status": "RESOURCE_EXHAUSTED"}})

    client.models.generate_content = over_limit

    with pytest.raises(ModelError, match="quota"):
        gemini(client)
