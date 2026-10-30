# One image for both cloud services: the web app (Mini App + API) and the 15-minute scheduler tick.
FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Dependencies first, so code changes don't reinstall them.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project

COPY alembic.ini ./
COPY migrations ./migrations
COPY src ./src
RUN uv sync --locked --no-dev

# Web service: bring the database schema up to date, then serve. The scheduler service overrides this
# with: python -m lecture_prep.tick
CMD ["sh", "-c", "alembic upgrade head && uvicorn lecture_prep.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
