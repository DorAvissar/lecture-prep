# lecture-prep

[![CI](https://github.com/DorAvissar/lecture-prep/actions/workflows/ci.yml/badge.svg)](https://github.com/DorAvissar/lecture-prep/actions/workflows/ci.yml)

A personal assistant that gets you ready for every lecture. Each morning it reads your Google Calendar,
finds the day's lectures, pulls the previous and current lecture material from OneDrive, and sends you on
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
    OD[OneDrive<br/>lecture files] --> Loc
    Loc --> Proc[Text extraction<br/>+ chunking + embeddings]
    Proc --> DB[(PostgreSQL<br/>+ pgvector)]
    Proc --> Sum[Summarizer<br/>Claude API]
    Sum --> DB
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
| Database | PostgreSQL + pgvector | One store for relational data and vector search |
| LLM | Claude API | Summaries and lecture-aware Q&A |
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

### Connecting OneDrive

Lecture files are read from OneDrive through Microsoft Graph, with read-only access (`Files.Read`).

1. In the [Microsoft Entra admin center](https://entra.microsoft.com/), open **App registrations → New
   registration**. Supported account types: *Accounts in any organizational directory and personal
   Microsoft accounts*. No redirect URI is needed.
2. Under **Authentication**, set **Allow public client flows** to *Yes* (enables the device-code sign-in).
3. Under **API permissions**, add *Microsoft Graph → Delegated → Files.Read*.
4. Copy the **Application (client) ID** into `MS_CLIENT_ID` in `.env`.
5. Sign in once - the token is cached in the git-ignored `.cache/` folder:

```bash
uv run python -m lecture_prep.onedrive.login
```

### Changing the database schema

```bash
# 1. edit the models in src/lecture_prep/db/models.py
uv run alembic revision --autogenerate -m "describe the change"
# 2. review the generated file in migrations/versions/ - autogenerate is a draft, not gospel
uv run alembic upgrade head
```

## Project structure

```
src/lecture_prep/     application code
src/lecture_prep/db/  database models and session
src/lecture_prep/onedrive/  Microsoft sign-in and OneDrive file access
migrations/           Alembic database migrations
tests/                pytest test suite
.github/workflows/    CI pipeline
```

## Roadmap

- [x] Project skeleton: FastAPI, tests, lint, CI, local database
- [x] Data model: courses, lectures, summaries (SQLAlchemy + Alembic)
- [ ] Calendar sync: today's lectures from Google Calendar
- [x] OneDrive client: list and download lecture files via Microsoft Graph
- [ ] Lecture locator: find the previous and current lecture for a course
- [ ] Processing: text extraction from PDF/PPTX, chunking, embeddings
- [ ] Summarizer: recap and prep prompts, with quality evals
- [ ] Scheduler + Telegram bot
- [ ] Telegram Mini App with lecture-aware chat (RAG)
- [ ] Cloud deployment
