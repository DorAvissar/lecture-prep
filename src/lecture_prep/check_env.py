"""Print which required settings reached the server - names only, never values - and stop if any is missing.

The cloud image runs this first, so a deploy without its variables fails with one clear line in the log
instead of a database traceback.
"""

import os
import sys

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from lecture_prep.config import normalize_database_url

REQUIRED = (
    "ENVIRONMENT",
    "DATABASE_URL",
    "TICK_SECRET",
    "GOOGLE_TOKEN_JSON",
    "CALENDAR_IDS",
    "GEMINI_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
)


def missing(environ: dict[str, str]) -> list[str]:
    return [name for name in REQUIRED if not environ.get(name, "").strip()]


def describe_database(raw: str) -> str:
    """Where DATABASE_URL points - host and database only, never the user or password."""
    try:
        url = make_url(normalize_database_url(raw))
    except ArgumentError:
        return "unreadable - re-paste DATABASE_URL from cloud.env"
    if not url.host:
        return "no host in DATABASE_URL - it would connect to localhost"
    return f"host {url.host}, database {url.database}"


def main() -> None:
    absent = missing(dict(os.environ))
    present = [name for name in REQUIRED if name not in absent]
    print(f"Settings present: {', '.join(present) or 'none'}")
    if "DATABASE_URL" in present:
        print(f"Database: {describe_database(os.environ['DATABASE_URL'])}")
    if absent:
        print(f"Settings MISSING: {', '.join(absent)} - add them in the host's environment variables.")
        sys.exit(1)


if __name__ == "__main__":
    main()
