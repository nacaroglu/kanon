import io
import json

from fastapi.testclient import TestClient

from kanon.api.app import create_app
from kanon.logging import configure_logging


def test_each_request_logs_one_json_line(monkeypatch, capsys):
    monkeypatch.setenv("KANON_DATABASE_URL", "postgresql://test/db")
    client = TestClient(create_app())
    capsys.readouterr()  # drop startup output

    client.get("/health")

    records = [json.loads(line) for line in capsys.readouterr().err.splitlines() if line.strip()]
    # The test client's own HTTP library also logs in-process; only count the app's lines.
    app_records = [r for r in records if r["logger"] == "kanon.request"]
    assert len(app_records) == 1
    record = app_records[0]
    assert record["method"] == "GET"
    assert record["path"] == "/health"
    assert record["status"] == 200
    assert record["duration_ms"] >= 0
    assert record["level"] == "INFO"


def test_log_level_from_settings_changes_output(monkeypatch, capsys):
    monkeypatch.setenv("KANON_DATABASE_URL", "postgresql://test/db")
    monkeypatch.setenv("KANON_LOG_LEVEL", "WARNING")
    client = TestClient(create_app())
    capsys.readouterr()

    client.get("/health")

    err = capsys.readouterr().err
    assert "kanon.request" not in err


def test_configure_logging_filters_by_level():
    stream = io.StringIO()
    configure_logging("WARNING", stream=stream)
    import logging

    logging.getLogger("t").info("hidden")
    logging.getLogger("t").warning("shown", extra={"document_id": 42})

    lines = stream.getvalue().strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["document_id"] == 42
