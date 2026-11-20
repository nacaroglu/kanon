import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from kanon.db import get_engine
from kanon.settings import Settings, get_settings


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch, tmp_path):
    """Keep tests independent of the real environment and any local `.env`."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("KANON_DATABASE_URL", raising=False)
    monkeypatch.delenv("KANON_LOG_LEVEL", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# --- Database fixtures -------------------------------------------------------
# Database tests need a real PostgreSQL. Point KANON_TEST_DATABASE_URL at a
# throwaway database; tests are skipped when it is not set.

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def test_database_url() -> str:
    url = os.environ.get("KANON_TEST_DATABASE_URL")
    if not url:
        pytest.skip("KANON_TEST_DATABASE_URL is not set; skipping database tests")
    return url


@pytest.fixture(scope="session")
def migrated_engine(test_database_url) -> Iterator[Engine]:
    """Apply all migrations to the test database once per test session."""
    previous = os.environ.get("KANON_DATABASE_URL")
    os.environ["KANON_DATABASE_URL"] = test_database_url  # read by alembic/env.py
    get_settings.cache_clear()
    try:
        cfg = Config(str(ROOT / "alembic.ini"))
        cfg.set_main_option("script_location", str(ROOT / "alembic"))
        command.upgrade(cfg, "head")
        yield get_engine(Settings(database_url=test_database_url))
    finally:
        if previous is None:
            os.environ.pop("KANON_DATABASE_URL", None)
        else:
            os.environ["KANON_DATABASE_URL"] = previous
        get_settings.cache_clear()


@pytest.fixture
def db_session(migrated_engine) -> Iterator[Session]:
    """A session wrapped in a transaction that is always rolled back."""
    connection = migrated_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
