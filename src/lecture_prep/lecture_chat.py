"""Answer questions about a lecture, with the lecture's own material as context.

Each request sends the PDFs of today's lecture and the one before it, then the conversation so far. The
PDFs come first, so providers that cache prompts (Claude) re-read them cheaply on follow-up questions.
The conversation itself is not stored: the page keeps it and sends it back each time.
"""

from collections.abc import Sequence

from lecture_prep.llm import ChatMessage, LectureFile, Model

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


class LectureChat:
    def __init__(self, model: Model) -> None:
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
        intro = f"Course: {course_name}. Today's lecture is lecture {number}"
        intro += f"; the files of lecture {number - 1} come first." if previous else "."
        first = ChatMessage("user", f"{intro}\n\n{history[0].content}")
        files = [*previous, *current]
        reply = self._model.generate(
            CHAT_SYSTEM_PROMPT, files, [first, *history[1:]], effort="medium", max_tokens=MAX_TOKENS
        )
        return reply.text
