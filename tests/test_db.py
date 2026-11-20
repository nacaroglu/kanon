from unittest.mock import MagicMock, patch

import pytest

from kanon.db import session_scope


def test_session_scope_commits_and_closes(monkeypatch):
    monkeypatch.setenv("KANON_DATABASE_URL", "postgresql://test/db")
    session = MagicMock()
    with patch("kanon.db.sessionmaker", return_value=lambda: session):
        with session_scope() as s:
            assert s is session

    session.commit.assert_called_once()
    session.close.assert_called_once()


def test_session_scope_rolls_back_on_error(monkeypatch):
    monkeypatch.setenv("KANON_DATABASE_URL", "postgresql://test/db")
    session = MagicMock()
    with patch("kanon.db.sessionmaker", return_value=lambda: session):
        with pytest.raises(RuntimeError):
            with session_scope():
                raise RuntimeError("boom")

    session.rollback.assert_called_once()
    session.commit.assert_not_called()
    session.close.assert_called_once()
