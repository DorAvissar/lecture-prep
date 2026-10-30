"""FastAPI entry point. Run locally with: uv run uvicorn lecture_prep.main:app --reload"""

from fastapi import FastAPI

from lecture_prep import __version__
from lecture_prep.config import get_settings
from lecture_prep.web.api import router as mini_app


def create_app() -> FastAPI:
    """Build the app. A factory (instead of a module-level app only) lets tests create fresh instances."""
    app = FastAPI(title="Lecture Prep", version=__version__)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__, "environment": get_settings().environment}

    app.include_router(mini_app)
    return app


app = create_app()
