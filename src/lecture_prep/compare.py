"""Compare models on one real lecture, blind:

    uv run python -m lecture_prep.compare "תכנות מערכות" 5

Writes the prep brief for lecture 5 and the recap of lecture 4 with every model in CANDIDATES, then saves
a page (comparisons/, git-ignored) that shows the versions as A, B, C in random order. Which model wrote
which is revealed only at the bottom, so the choice is made on the text alone. Summaries the configured
Claude model already wrote are reused from the database; nothing new is stored.
"""

import html
import logging
import random
import sys
from pathlib import Path

from sqlalchemy import select

from lecture_prep.config import get_settings
from lecture_prep.db.models import Course, Lecture, Summary, SummaryKind
from lecture_prep.db.session import SessionLocal
from lecture_prep.google_api.drive import DriveClient
from lecture_prep.lecture_locator import course_lectures
from lecture_prep.llm import LectureFile, make_model
from lecture_prep.summarizer import Summarizer
from lecture_prep.web.render import render_markdown

OUTPUT_DIR = Path("comparisons")
# (name shown when revealed, provider, model id or None for the one in settings)
CANDIDATES = [
    ("Claude Opus 5.5", "claude", None),
    ("Claude Sonnet 5.5", "claude", "claude-sonnet-5-5"),
    ("Gemini Pro", "gemini", None),
]
PAGE_STYLE = (Path(__file__).parent / "web" / "static" / "app.html").read_text(encoding="utf-8")
PAGE_STYLE = PAGE_STYLE[PAGE_STYLE.index("<style>") : PAGE_STYLE.index("</style>") + len("</style>")]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    for noisy in ("httpx", "httpx2", "anthropic", "google_genai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    course_name, number = sys.argv[1], int(sys.argv[2])
    settings = get_settings()

    with DriveClient.from_settings(settings) as drive, SessionLocal() as session:
        course = session.scalars(select(Course).where(Course.name == course_name)).one()
        lectures = course_lectures(drive, course)
        jobs = [(SummaryKind.PREP, number), (SummaryKind.RECAP, number - 1)]
        versions: dict[SummaryKind, dict[str, str]] = {}
        for kind, lecture_number in jobs:
            material = lectures.get(lecture_number)
            if material is None:
                continue
            files = [LectureFile(item.name, drive.download(item)) for item in material.files]
            stored = session.scalar(
                select(Summary)
                .join(Lecture)
                .where(Lecture.course_id == course.id, Lecture.number == lecture_number, Summary.kind == kind)
            )
            versions[kind] = {}
            for name, provider, model in CANDIDATES:
                if provider == "claude" and model is None and stored is not None:
                    versions[kind][name] = stored.content  # already written by the configured model
                    continue
                result = Summarizer(make_model(settings, provider, model)).summarize(kind, course.name, files)
                versions[kind][name] = result.content

    path = OUTPUT_DIR / f"{course_name}-{number}.html"
    OUTPUT_DIR.mkdir(exist_ok=True)
    path.write_text(blind_page(course_name, number, versions), encoding="utf-8")
    print(f"Saved {path.resolve()}")


def blind_page(course_name: str, number: int, versions: dict[SummaryKind, dict[str, str]]) -> str:
    names = list(next(iter(versions.values())))
    random.shuffle(names)  # the letters are random, so the reader cannot guess
    labels = dict(zip("ABCDEFG", names, strict=False))
    titles = {SummaryKind.PREP: f"הכנה להרצאה {number}", SummaryKind.RECAP: f"חזרה על הרצאה {number - 1}"}

    sections = []
    for kind, by_provider in versions.items():
        sections.append(f"<h2>{titles[kind]}</h2>")
        for label, provider in labels.items():
            sections.append(
                f'<div class="version"><h4>גרסה {label}</h4>{render_markdown(by_provider[provider])}</div>'
            )

    reveal = "<br>".join(f"גרסה {label}: <bdi>{name}</bdi>" for label, name in labels.items())
    return f"""<!doctype html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>השוואה: {html.escape(course_name)} {number}</title>
{PAGE_STYLE}
<style>
  main {{ padding-bottom: 40px; }}
  h2 {{ margin: 28px 0 8px; }}
  .version {{ border: 1px solid var(--surface); border-radius: 14px; padding: 4px 16px 8px; margin: 12px 0; }}
  .version h4 {{ margin: 12px 0 0; color: var(--accent); }}
  details {{ margin-top: 28px; font-size: 18px; }}
</style>
</head>
<body>
<header>
<h1>{html.escape(course_name)}</h1>
<p>השוואה עיוורת: קראו את שתי הגרסאות ובחרו, ורק אז גלו מי כתב מה.</p>
</header>
<main>
{"".join(sections)}
<details><summary>מי כתב מה?</summary><p>{reveal}</p></details>
</main>
</body>
</html>
"""


if __name__ == "__main__":
    main()
