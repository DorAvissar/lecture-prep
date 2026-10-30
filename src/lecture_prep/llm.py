"""One small interface for the language model, so Claude and Gemini are interchangeable.

The summarizer and the lecture chat decide *what* to ask (system prompt, lecture PDFs, conversation);
a Model decides *how* to ask its provider. LLM_PROVIDER in .env picks the provider.
"""

import base64
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

import anthropic
from anthropic.types.beta import BetaContentBlockParam, BetaMessageParam
from google import genai
from google.genai import types as genai_types

from lecture_prep.config import Settings

log = logging.getLogger(__name__)

Effort = Literal["low", "medium", "high"]

# Claude: on a safety decline, the API re-runs the request on a suitable fallback model in the same call.
CLAUDE_FALLBACK_BETA = "server-side-fallback-2026-07-01"


@dataclass(frozen=True)
class LectureFile:
    name: str
    pdf: bytes


@dataclass(frozen=True)
class ChatMessage:
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True)
class Reply:
    text: str
    model: str  # the model that actually answered


class ModelError(RuntimeError):
    """The model did not produce a usable answer."""


class Model(Protocol):
    def generate(
        self,
        system: str,
        files: Sequence[LectureFile],
        turns: Sequence[ChatMessage],
        effort: Effort,
        max_tokens: int,
    ) -> Reply:
        """Answer the last turn. `files` go before the text of the first turn, which must be the user's."""
        ...


class ClaudeModel:
    def __init__(self, client: anthropic.Anthropic, model: str) -> None:
        self._client = client
        self._model = model

    def generate(
        self,
        system: str,
        files: Sequence[LectureFile],
        turns: Sequence[ChatMessage],
        effort: Effort,
        max_tokens: int,
    ) -> Reply:
        # Long PDFs make for slow requests; streaming keeps the connection from timing out.
        with self._client.beta.messages.stream(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=claude_messages(files, turns),
            output_config={"effort": effort},
            betas=[CLAUDE_FALLBACK_BETA],
            fallbacks="default",
        ) as stream:
            message = stream.get_final_message()

        usage = message.usage
        log.info(
            "%s: %d input (+%d written to cache, %d read from cache), %d output tokens",
            message.model,
            usage.input_tokens,
            usage.cache_creation_input_tokens or 0,
            usage.cache_read_input_tokens or 0,
            usage.output_tokens,
        )
        if message.stop_reason == "refusal":
            raise ModelError(f"the model declined ({message.stop_details})")
        if message.stop_reason == "max_tokens":
            raise ModelError("the answer was cut off at the token limit")
        text = "".join(block.text for block in message.content if block.type == "text").strip()
        if not text:
            raise ModelError("the model returned an empty answer")
        return Reply(text=text, model=message.model)


def claude_messages(files: Sequence[LectureFile], turns: Sequence[ChatMessage]) -> list[BetaMessageParam]:
    """The PDFs, then the first turn's text; the PDFs are marked for prompt caching."""
    documents: list[BetaContentBlockParam] = [
        {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": base64.standard_b64encode(file.pdf).decode("ascii"),
            },
            "title": file.name,
        }
        for file in files
    ]
    if documents:
        documents[-1]["cache_control"] = {"type": "ephemeral"}  # everything up to here is cached
    first, *rest = turns
    messages: list[BetaMessageParam] = [
        {"role": "user", "content": [*documents, {"type": "text", "text": first.content}]}
    ]
    messages += [{"role": turn.role, "content": turn.content} for turn in rest]
    return messages


# Gemini has no "effort" setting by that name; the thinking level plays the same role.
GEMINI_THINKING = {"low": "LOW", "medium": "MEDIUM", "high": "HIGH"}
GEMINI_FAILURES = {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII", "OTHER"}


class GeminiModel:
    def __init__(self, client: genai.Client, model: str) -> None:
        self._client = client
        self._model = model

    def generate(
        self,
        system: str,
        files: Sequence[LectureFile],
        turns: Sequence[ChatMessage],
        effort: Effort,
        max_tokens: int,
    ) -> Reply:
        response = self._client.models.generate_content(
            model=self._model,
            contents=gemini_contents(files, turns),
            config=genai_types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=max_tokens,
                thinking_config=genai_types.ThinkingConfig(thinking_level=GEMINI_THINKING[effort]),
            ),
        )
        usage = response.usage_metadata
        if usage is not None:
            log.info(
                "%s: %d input (%d from cache), %d output + %d thinking tokens",
                self._model,
                usage.prompt_token_count or 0,
                usage.cached_content_token_count or 0,
                usage.candidates_token_count or 0,
                usage.thoughts_token_count or 0,
            )
        reason = response.candidates[0].finish_reason if response.candidates else None
        reason_name = getattr(reason, "name", str(reason))
        if reason_name in GEMINI_FAILURES:
            raise ModelError(f"the model stopped: {reason_name}")
        if reason_name == "MAX_TOKENS":
            raise ModelError("the answer was cut off at the token limit")
        text = (response.text or "").strip()
        if not text:
            raise ModelError("the model returned an empty answer")
        return Reply(text=text, model=self._model)


def gemini_contents(files: Sequence[LectureFile], turns: Sequence[ChatMessage]) -> list[genai_types.Content]:
    first, *rest = turns
    pdfs = [genai_types.Part.from_bytes(data=file.pdf, mime_type="application/pdf") for file in files]
    contents = [
        genai_types.Content(role="user", parts=[*pdfs, genai_types.Part.from_text(text=first.content)])
    ]
    contents += [
        genai_types.Content(
            role="model" if turn.role == "assistant" else "user",  # Gemini calls the assistant "model"
            parts=[genai_types.Part.from_text(text=turn.content)],
        )
        for turn in rest
    ]
    return contents


def make_model(settings: Settings, provider: str | None = None, model: str | None = None) -> Model:
    """The model chosen in settings, or another `provider` / `model` (to compare)."""
    provider = provider or settings.llm_provider
    if provider == "gemini":
        if settings.gemini_api_key is None:
            raise ModelError("set GEMINI_API_KEY in .env to use Gemini")
        client = genai.Client(api_key=settings.gemini_api_key.get_secret_value())
        return GeminiModel(client, model or settings.gemini_model)
    api_key = settings.anthropic_api_key.get_secret_value() if settings.anthropic_api_key else None
    claude_client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
    return ClaudeModel(claude_client, model or settings.anthropic_model)
