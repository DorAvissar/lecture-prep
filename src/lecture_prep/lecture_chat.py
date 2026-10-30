"""Answer questions about a lecture, with the lecture's own material as context.

Each request sends the PDFs of today's lecture and the one before it, then the conversation so far. The
PDFs come first and are marked for prompt caching, so follow-up questions re-read them at a fraction of
the price. The conversation itself is not stored: the page keeps it and sends it back each time.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import anthropic
from anthropic.types.beta import BetaContentBlockParam, BetaMessageParam

from lecture_prep.summarizer import FALLBACK_BETA, LectureFile, SummaryError, lecture_documents

log = logging.getLogger(__name__)

MAX_TOKENS = 16000

CHAT_SYSTEM_PROMPT = """\
You are a patient tutor for a university student. You have the material of today's lecture and the \
lecture before it (PDF files). Answer the student's questions about it.

- Answer the question that was asked, briefly: usually two to six short sentences. Go longer only when \
the student asks for more detail or an example.
- Explain with intuition first: what it means and why, then the formal side if needed. A short analogy \
or a tiny example often helps.
- Ground answers in the lecture material and say when something goes beyond it.

The answer is shown in a right-to-left page, where mixed Hebrew and English on one line gets scrambled:
- Write in Hebrew. Put every English word, technical term, identifier, formula and piece of code inside \
backticks, e.g. `pointer`, `O(n)`. Never start a line with an English word.
- Code only as a separate fenced block, when it truly helps.
- Use **bold** and `-` bullets sparingly. No tables."""


@dataclass(frozen=True)
class ChatMessage:
    role: Literal["user", "assistant"]
    content: str


class LectureChat:
    def __init__(self, client: anthropic.Anthropic, model: str) -> None:
        self._client = client
        self._model = model

    def answer(
        self,
        course_name: str,
        number: int,
        current: Sequence[LectureFile],
        previous: Sequence[LectureFile],
        history: Sequence[ChatMessage],
    ) -> str:
        """Answer the last message in `history`, which must be the student's question."""
        if not history or history[-1].role != "user":
            raise ValueError("the conversation must end with a question")
        with self._client.beta.messages.stream(
            model=self._model,
            max_tokens=MAX_TOKENS,
            system=CHAT_SYSTEM_PROMPT,
            messages=build_messages(course_name, number, current, previous, history),
            output_config={"effort": "medium"},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        ) as stream:
            message = stream.get_final_message()

        usage = message.usage
        log.info(
            "chat for %s %d: %d input (%d from cache), %d output tokens",
            course_name,
            number,
            usage.input_tokens,
            usage.cache_read_input_tokens or 0,
            usage.output_tokens,
        )
        if message.stop_reason == "refusal":
            raise SummaryError("the model declined to answer")
        text = "".join(block.text for block in message.content if block.type == "text").strip()
        if not text:
            raise SummaryError("the model returned an empty answer")
        return text


def build_messages(
    course_name: str,
    number: int,
    current: Sequence[LectureFile],
    previous: Sequence[LectureFile],
    history: Sequence[ChatMessage],
) -> list[BetaMessageParam]:
    """The material and a short intro go before the first question; the rest of the chat follows."""
    documents = lecture_documents([*previous, *current])
    if documents:
        documents[-1]["cache_control"] = {"type": "ephemeral"}  # everything up to here is cached
    intro = f"Course: {course_name}. Today's lecture is lecture {number}"
    intro += f"; the files of lecture {number - 1} come first." if previous else "."
    first: list[BetaContentBlockParam] = [
        *documents,
        {"type": "text", "text": intro},
        {"type": "text", "text": history[0].content},
    ]
    messages: list[BetaMessageParam] = [{"role": "user", "content": first}]
    messages += [{"role": message.role, "content": message.content} for message in history[1:]]
    return messages
