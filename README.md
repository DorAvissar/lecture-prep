# lecture-prep

[![CI](https://github.com/DorAvissar/lecture-prep/actions/workflows/ci.yml/badge.svg)](https://github.com/DorAvissar/lecture-prep/actions/workflows/ci.yml)

A personal assistant that gets you ready for every lecture. Each morning it reads your Google Calendar,
finds the day's lectures, pulls the previous and current lecture material from Google Drive, and sends you on
Telegram:

- **A recap** of the previous lecture: short, focused on what you need to remember.
- **A prep brief** for today's lecture: the big picture and the *intuition* behind each idea, without
  drowning in details.
- **A chat** where you can ask questions, answered in the context of that lecture's material.

> **Status:** early development. See the [roadmap](#roadmap).

## Architecture

```mermaid
flowchart LR
    Cal[Google Calendar] --> Sched[Scheduler<br/>07:00 + before each lecture]
    Sched --> Loc[Lecture Locator]
    GD[Google Drive<br/>lecture PDFs] --> Loc
    Loc --> Sum[Summarizer<br/>Claude API, reads the PDFs]
    Sum --> DB[(PostgreSQL)]
    Sum --> TG[Telegram Bot]
    TG --> Mini[Telegram Mini App<br/>summary + chat]
    Mini --> API[FastAPI]
    API --> DB
```

## Tech stack

| Area | Choice | Why |
|---|---|---|
| Language / API | Python 3.11, FastAPI | Strong AI/data ecosystem, typed, async-ready |
| Packaging | [uv](https://docs.astral.sh/uv/) | Fast, reproducible installs via `uv.lock` |
| Database | PostgreSQL | Courses, lectures and stored summaries |
| LLM | Claude API (Claude Opus 5.5) | Reads lecture PDFs directly - slides, formulas and diagrams included |
| Delivery | Telegram Bot + Mini App | Free push notifications and a custom UI without an app store |
| Quality | pytest, ruff, pre-commit, GitHub Actions | Tests and lint on every commit and push |

## Getting started

Prerequisites: [uv](https://docs.astral.sh/uv/getting-started/installation/) and
[Docker](https://www.docker.com/products/docker-desktop/).

```bash
git clone https://github.com/DorAvissar/lecture-prep.git
cd lecture-prep
uv sync                       # create .venv and install dependencies
uv run pre-commit install     # run ruff before every commit
cp .env.example .env          # then fill in real values
docker compose up -d          # start Postgres + pgvector
uv run alembic upgrade head   # create / update the database tables
uv run uvicorn lecture_prep.main:app --reload
```

Then open <http://localhost:8000/health> or the interactive API docs at <http://localhost:8000/docs>.

### Running checks

```bash
uv run pytest                 # tests (needs the database from docker compose)
uv run ruff check .           # lint
uv run ruff format .          # format
uv run alembic check          # models and migrations are in sync
```

Database tests run the real migrations, then wrap every test in a transaction that is rolled back, so
they never leave data behind.

### Connecting Google

The calendar and the lecture files both come from Google, through one read-only sign-in
(`calendar.readonly` + `drive.readonly`).

1. In [Google Cloud Console](https://console.cloud.google.com/), create a project.
2. **APIs & Services → Library**: enable the *Google Calendar API* and the *Google Drive API*.
3. **Google Auth Platform → Get started**: audience *External*. Under **Audience**, add your own Gmail
   address as a test user.
4. **Clients → Create client**, type *Desktop app*. Download the JSON file and save it as
   `.secrets/google_client_secret.json` (git-ignored).
5. Sign in once - a browser window opens, and the token is saved to the git-ignored `.cache/` folder:

```bash
uv run python -m lecture_prep.google_api.login
```

> While the app's publishing status is *Testing*, Google expires the refresh token after 7 days. For a
> personal tool, set **Audience → Publish app** to *In production*; Google then shows an "unverified app"
> warning on the consent screen, which you can accept for your own account.

Lecture files live in Google Drive under `DRIVE_LECTURES_FOLDER` (default `Lectures`), one sub-folder per
course. With [Google Drive for desktop](https://www.google.com/drive/download/) that folder is a normal
folder on your computer.

### Courses and lecture files

Each course has a folder in Drive. Every file in it **starts with its lecture number**; files with the
same number belong to the same lecture. Only PDFs and native Google docs are used (save `.pptx` slides as
PDF). The highest number is today's lecture, the one below it is the previous lecture.

```
Lectures/
  Calculus 2/
    01 - Limits.pdf
    02 - Derivatives.pdf
    02 - Derivatives (notes).pdf
    03 - Integrals.pdf
```

List your courses in `courses.toml` (copy `courses.example.toml`), then load them:

```bash
uv run python -m lecture_prep.courses
```

### Running a day

Put a Claude API key in `.env` (`ANTHROPIC_API_KEY`), then:

```bash
uv run python -m lecture_prep.run_day               # today
uv run python -m lecture_prep.run_day 2026-11-02    # another day
```

For each lecture on the calendar it writes a recap of the previous lecture and a prep brief for today's,
stores them, and prints them. Stored summaries are reused, so a second run costs nothing.

### Changing the database schema

```bash
# 1. edit the models in src/lecture_prep/db/models.py
uv run alembic revision --autogenerate -m "describe the change"
# 2. review the generated file in migrations/versions/ - autogenerate is a draft, not gospel
uv run alembic upgrade head
```

## Project structure

```
src/lecture_prep/             application code: lecture locator, summarizer, daily pipeline
src/lecture_prep/db/          database models and session
src/lecture_prep/google_api/  Google sign-in, Drive client (and Calendar sync)
migrations/                   Alembic database migrations
tests/                        pytest test suite
.github/workflows/            CI pipeline
```

## Roadmap

- [x] Project skeleton: FastAPI, tests, lint, CI, local database
- [x] Data model: courses, lectures, summaries (SQLAlchemy + Alembic)
- [x] Calendar sync: today's lectures from Google Calendar
- [x] Google sign-in + Drive client: list and download lecture files
- [x] Lecture locator: find the previous and current lecture for a course
- [x] Summarizer: recap and prep prompts, lecture PDFs sent to Claude directly
- [x] Daily pipeline: calendar -> files -> stored summaries
- [ ] Summary quality evals
- [ ] Scheduler + Telegram bot
- [ ] Telegram Mini App with lecture-aware chat
- [ ] Cloud deployment
