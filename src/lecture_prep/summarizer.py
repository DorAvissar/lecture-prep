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
and/or notes, as PDF files) and write a short summary that the student reads on their phone, in a \
right-to-left page, a few minutes before class.

What makes it good:
- The main idea comes through. Someone who reads only the opening line knows what the lecture is about.
- It builds intuition: what an idea means and why it is needed, in plain words, often through a short \
analogy or a tiny concrete example. Formal definitions, proofs and long code belong in the lecture itself.
- It is easy on the eye: short paragraphs of one to three sentences, a bold title per idea, plenty of \
white space. No walls of text.
- It is concise without losing substance: every sentence earns its place.

Language and layout (the page is right-to-left, and mixed Hebrew and English on one line gets scrambled):
- Write in Hebrew.
- Put every English word, technical term, identifier, formula and piece of code inside backticks, e.g. \
`memory leak`, `new`, `O(n)`. Never write bare English words inside a Hebrew sentence.
- Never start a line, heading or bullet with an English word; start with Hebrew.
- When a term matters, give the Hebrew first and the original term in backticks after it, once.
- Code only when a single line truly helps, as a separate fenced block of at most three lines.
- Use `###` headings, `**bold**`, and `-` bullets. No tables, no numbered sub-levels, no emojis.

Base everything on the material. If something in it is unclear (for example handwriting), skip it rather \
than guess."""

INSTRUCTIONS = {
    SummaryKind.RECAP: """\
This lecture already happened. Write a recap the student reads right before the next lecture, so they \
walk in remembering where the course stands.

Structure:
- `### בשורה אחת`: one sentence with the lecture's main idea.
- `### מה למדנו`: the three to five ideas that matter most. For each: a bold title, then one or two \
sentences on what it is and why it matters.
- `### הקשר להמשך`: one or two sentences on what the next lecture is likely to build on.

Length: 200-350 words.""",
    SummaryKind.PREP: """\
This lecture happens today and the student has not seen it yet. Write a prep brief that lets them follow \
the lecture with the big picture already in mind.

Structure:
- `### הרעיון המרכזי`: the question or problem this lecture answers, and why anyone would care, in two \
sentences.
- `### מה נלמד`: the three to five main ideas, in the order they come. For each: a bold title, then two \
or three sentences of intuition (what it means, why it works, how it connects to what came before). Use \
an analogy or a tiny example where it makes the idea click.
- `### לשים לב בהרצאה`: two or three short bullets on what to pay attention to.

Length: 250-400 words.""",
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
