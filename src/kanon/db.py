"""Database engine and session wiring (synchronous SQLAlchemy 2.x, psycopg 3)."""

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from kanon.settings import Settings, get_settings


@lru_cache
def _engine_for(database_url: str) -> Engine:
    # SQLAlchemy selects the psycopg 3 driver with the `postgresql+psycopg` scheme.
    url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 3})


def get_engine(settings: Settings | None = None) -> Engine:
    settings = settings or get_settings()
    return _engine_for(settings.database_url)


def get_session(settings: Annotated[Settings, Depends(get_settings)]) -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed afterwards."""
    session = sessionmaker(bind=get_engine(settings), expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context manager for code outside request handlers (CLI, jobs).

    Commits on success, rolls back on error, always closes.
    """
    session = sessionmaker(bind=get_engine(), expire_on_commit=False)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
