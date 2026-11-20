import os
import shutil
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
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


# --- Sample procedure repository ---------------------------------------------
# Built from fixtures/sample-procedures by scripts/make-sample-repo.sh. The
# script fixes author, committer, dates and messages, so the hashes below are
# stable; if you change the fixture content, update them (the test that pins
# them will tell you the new values).


@dataclass(frozen=True)
class SampleRepo:
    path: Path
    head: str  # newest commit
    commits: tuple[str, ...]  # oldest first
    procedure_paths: tuple[str, ...]  # at HEAD, sorted


SAMPLE_COMMITS = (
    "c8ddb7613fe0523249a0d926efa15a9e856ba001",  # 2026-01-05 expense reports
    "17ef3a6cbd7331f21eb9412dcc64619685251925",  # 2026-02-10 remote work
    "f41aeea2399b44ddcde3d0d37987afc560bfb981",  # 2026-03-16 incident response
)
SAMPLE_PROCEDURE_PATHS = (
    "procedures/expense-reports.md",
    "procedures/incident-response.md",
    "procedures/remote-work.md",
)


def build_sample_repo(destination: Path) -> str:
    """Create the sample repository at `destination` and return its HEAD hash."""
    if shutil.which("git") is None or shutil.which("bash") is None:
        pytest.skip("git and bash are required to build the sample repository")
    result = subprocess.run(
        ["bash", str(ROOT / "scripts" / "make-sample-repo.sh"), str(destination)],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


@pytest.fixture
def sample_repo(tmp_path_factory) -> SampleRepo:
    """A fresh copy of the deterministic sample repository in a temporary directory."""
    path = tmp_path_factory.mktemp("sample") / "repo"
    head = build_sample_repo(path)
    return SampleRepo(
        path=path,
        head=head,
        commits=SAMPLE_COMMITS,
        procedure_paths=SAMPLE_PROCEDURE_PATHS,
    )
