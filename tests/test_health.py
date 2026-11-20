from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from kanon.api.app import create_app
from kanon.db import get_session


def make_client(session):
    app = create_app()
    closed = []

    def override():
        try:
            yield session
        finally:
            closed.append(True)
            session.close()

    app.dependency_overrides[get_session] = override
    return TestClient(app), closed


def test_health_reports_database_ok(monkeypatch):
    monkeypatch.setenv("KANON_DATABASE_URL", "postgresql://test/db")
    session = MagicMock()
    client, closed = make_client(session)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
    session.close.assert_called_once()
    assert closed == [True]


def test_health_degraded_when_database_down(monkeypatch):
    monkeypatch.setenv("KANON_DATABASE_URL", "postgresql://test/db")
    session = MagicMock()
    session.execute.side_effect = OperationalError("SELECT 1", {}, Exception("down"))
    client, _ = make_client(session)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "degraded", "database": "unreachable"}
    session.close.assert_called_once()
