from fastapi.testclient import TestClient

from kanon.api.app import create_app


def test_health_returns_ok(monkeypatch):
    monkeypatch.setenv("KANON_DATABASE_URL", "postgresql://test/db")
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
