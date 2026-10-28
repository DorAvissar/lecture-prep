"""Engine and session factory. The engine connects lazily, on first use."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from lecture_prep.config import get_settings

engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """Yield a session and always close it - usable as a FastAPI dependency."""
    with SessionLocal() as session:
        yield session
