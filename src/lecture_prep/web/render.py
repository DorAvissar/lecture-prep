"""Render the model's markdown as HTML for the right-to-left Mini App page.

Mixed Hebrew and English on one line gets scrambled by the browser's bidi algorithm, so every run of
Latin text and every piece of code is wrapped in an isolated left-to-right element (<bdi>, or <code>
styled with unicode-bidi: isolate). The Hebrew around it then keeps its order.

Only the small subset the summaries use is supported: ### headings, **bold**, `code`, - bullets,
fenced code blocks and paragraphs.
"""

import html
import re

HEADING = re.compile(r"^#{1,6}\s+(.+)$")
BULLET = re.compile(r"^\s*[-*]\s+(.+)$")
FENCE = re.compile(r"^\s*```")
CODE_SPAN = re.compile(r"`([^`]+)`")
# A run of Latin text: starts and ends with a Latin letter or digit, may contain spaces and punctuation.
LATIN_RUN = re.compile(r"[A-Za-z][A-Za-z0-9 _.,:;'\"()\[\]{}<>=+\-/\\&|!?%^~#@$]*[A-Za-z0-9)\]}+#]|[A-Za-z]")
BOLD = re.compile(r"\*\*(.+?)\*\*")


def render_inline(text: str) -> str:
    parts = []
    position = 0
    for match in CODE_SPAN.finditer(text):
        parts.append(_render_text(text[position : match.start()]))
        parts.append(f"<code>{html.escape(match.group(1))}</code>")
        position = match.end()
    parts.append(_render_text(text[position:]))
    return "".join(parts)


def _render_text(text: str) -> str:
    """Escape plain text, isolate its Latin runs, then apply **bold**."""
    out = []
    position = 0
    for match in LATIN_RUN.finditer(text):
        out.append(html.escape(text[position : match.start()]))
        out.append(f"<bdi>{html.escape(match.group())}</bdi>")
        position = match.end()
    out.append(html.escape(text[position:]))
    return BOLD.sub(r"<b>\1</b>", "".join(out))


def render_markdown(markdown: str) -> str:
    blocks: list[str] = []
    paragraph: list[str] = []
    bullets: list[str] = []
    code: list[str] | None = None

    def flush() -> None:
        if paragraph:
            blocks.append("<p>" + "<br>".join(render_inline(line) for line in paragraph) + "</p>")
            paragraph.clear()
        if bullets:
            blocks.append("<ul>" + "".join(f"<li>{render_inline(item)}</li>" for item in bullets) + "</ul>")
            bullets.clear()

    for line in markdown.strip().splitlines():
        if code is not None:
            if FENCE.match(line):
                blocks.append(f'<pre dir="ltr"><code>{html.escape(chr(10).join(code))}</code></pre>')
                code = None
            else:
                code.append(line)
        elif FENCE.match(line):
            flush()
            code = []
        elif not line.strip():
            flush()
        elif heading := HEADING.match(line):
            flush()
            blocks.append(f"<h3>{render_inline(heading.group(1))}</h3>")
        elif bullet := BULLET.match(line):
            if paragraph:
                flush()
            bullets.append(bullet.group(1))
        else:
            if bullets:
                flush()
            paragraph.append(line.strip())
    if code is not None:  # an unclosed fence: show what we have
        blocks.append(f'<pre dir="ltr"><code>{html.escape(chr(10).join(code))}</code></pre>')
    flush()
    return "\n".join(blocks)
