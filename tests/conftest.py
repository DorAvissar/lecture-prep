"""Shared pytest fixtures."""

from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from lecture_prep.config import get_settings


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    """Bring the database schema up to date once per test run, using the real migrations."""
    engine = create_engine(get_settings().database_url, connect_args={"connect_timeout": 3})
    try:
        with engine.connect():
            pass
    except OperationalError:
        pytest.fail("Database is not reachable. Start it with: docker compose up -d", pytrace=False)
    command.upgrade(Config("alembic.ini"), "head")
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(engine: Engine) -> Iterator[Session]:
    """A session whose changes are rolled back after each test, so tests never leave data behind."""
    with engine.connect() as connection:
        transaction = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint")
        yield session
        session.close()
        transaction.rollback()
