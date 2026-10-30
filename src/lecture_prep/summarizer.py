"""Write lecture summaries with Claude. The lecture's PDFs go to the model as-is - slides, formulas and
diagrams included - so there is no text-extraction step.

Two kinds of summary (see SummaryKind):
- recap: the previous lecture, so you remember where the course stands.
- prep: today's lecture, the big picture and the intuition behind each idea.
"""

import base64
import logging
from collections.abc import Sequence
from dataclasses import dataclass

import anthropic
from anthropic.types.beta import BetaContentBlockParam

from lecture_prep.db.models import SummaryKind

log = logging.getLogger(__name__)

MAX_TOKENS = 32000
# On a safety decline, the API re-runs the request on a suitable fallback model inside the same call.
FALLBACK_BETA = "server-side-fallback-2026-07-01"

SYSTEM_PROMPT = """\
You help a university student get ready for lectures. You receive the material of one lecture (slides \
and/or summaries, as PDF files) and write a summary of it for the student to read on their phone.

Write in Hebrew. Keep technical terms, formulas and code as they appear in the material. Use short \
paragraphs, markdown headings and bullet lists; no tables, since they render badly on a phone. Write \
formulas in plain text or simple LaTeX between $ signs.

Base everything on the material. If the material is thin or unclear on a point, say so briefly instead \
of filling the gap with guesses."""

INSTRUCTIONS = {
    SummaryKind.RECAP: """\
This lecture already happened. Write a recap the student reads a few minutes before the next lecture \
of the course, so they remember where things stand.

- Open with two or three sentences on what the lecture was about.
- Cover every main topic: the key definitions, results and methods, each with one line on why it matters.
- End with the points the next lecture is most likely to build on.

Be complete but not long: about 400-700 words. Leave out proofs and worked examples unless one is \
central to understanding.""",
    SummaryKind.PREP: """\
This lecture happens today and the student has not seen it yet. Write a prep brief that gives them the \
big picture before they walk in.

- Open with the one question or problem this lecture answers, and why anyone would care.
- For each main idea, explain the intuition: what it means, why it works, how it connects to what came \
before. Prefer a good analogy or a small example over formal detail.
- Do not reproduce definitions, proofs or derivations in full - the lecture will do that. Name them so \
the student recognises them.
- End with two or three things to pay attention to during the lecture.

Keep it light: about 300-500 words.""",
}


@dataclass(frozen=True)
class LectureFile:
    name: str
    pdf: bytes


@dataclass(frozen=True)
class SummaryResult:
    content: str
    model: str  # the model that actually wrote it - a fallback model if the first one declined


class SummaryError(RuntimeError):
    """The model did not produce a usable summary."""


def lecture_documents(files: Sequence[LectureFile]) -> list[BetaContentBlockParam]:
    """The lecture's PDFs as document blocks, titled by file name."""
    return [
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


class Summarizer:
    def __init__(self, client: anthropic.Anthropic, model: str) -> None:
        self._client = client
        self._model = model

    def summarize(self, kind: SummaryKind, course_name: str, files: Sequence[LectureFile]) -> SummaryResult:
        if not files:
            raise ValueError("a lecture needs at least one file to summarize")
        content: list[BetaContentBlockParam] = [
            *lecture_documents(files),
            {"type": "text", "text": f"Course: {course_name}\n\n{INSTRUCTIONS[kind]}"},
        ]
        # Long PDFs make for slow requests; streaming keeps the connection from timing out.
        with self._client.beta.messages.stream(
            model=self._model,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
            output_config={"effort": "high"},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        ) as stream:
            message = stream.get_final_message()
        usage = message.usage
        log.info(
            "%s for %s: %d input tokens, %d output tokens (%s)",
            kind,
            course_name,
            usage.input_tokens,
            usage.output_tokens,
            message.model,
        )

        if message.stop_reason == "refusal":
            raise SummaryError(f"the model declined to summarize this lecture ({message.stop_details})")
        if message.stop_reason == "max_tokens":
            raise SummaryError("the summary was cut off at the token limit")
        text = "".join(block.text for block in message.content if block.type == "text").strip()
        if not text:
            raise SummaryError("the model returned an empty summary")
        return SummaryResult(content=text, model=message.model)


def claude_client(api_key: str | None) -> anthropic.Anthropic:
    """An Anthropic client; with no key, the SDK reads ANTHROPIC_API_KEY or a stored login itself."""
    return anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
