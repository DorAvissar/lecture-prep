"""Shared pytest fixtures."""

from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import URL, Engine, create_engine, make_url, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from lecture_prep.config import get_settings


def testing_database_url() -> URL:
    """The app's database name with "_test" added, on the same server - tests never touch your real data."""
    url = make_url(get_settings().database_url)
    return url.set(database=f"{url.database}_test")


def create_database_if_missing(url: URL) -> None:
    server = create_engine(
        url.set(database="postgres"), isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 3}
    )
    try:
        with server.connect() as connection:
            exists = connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database}
            )
            if not exists:
                connection.execute(text(f'CREATE DATABASE "{url.database}"'))
    except OperationalError:
        pytest.fail("Database is not reachable. Start it with: docker compose up -d", pytrace=False)
    finally:
        server.dispose()


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    """Create the test database if needed and bring its schema up to date with the real migrations."""
    url = testing_database_url()
    create_database_if_missing(url)
    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", url.render_as_string(hide_password=False))
    command.upgrade(alembic_config, "head")
    engine = create_engine(url)
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
