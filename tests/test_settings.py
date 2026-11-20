import pytest
from pydantic import ValidationError

from kanon.settings import Settings


def test_defaults_and_required_value(monkeypatch):
    monkeypatch.setenv("KANON_DATABASE_URL", "postgresql://x/y")

    settings = Settings()

    assert settings.database_url == "postgresql://x/y"
    assert settings.log_level == "INFO"


def test_environment_overrides_default(monkeypatch):
    monkeypatch.setenv("KANON_DATABASE_URL", "postgresql://x/y")
    monkeypatch.setenv("KANON_LOG_LEVEL", "DEBUG")

    assert Settings().log_level == "DEBUG"


def test_explicit_override_does_not_touch_environment():
    settings = Settings(database_url="postgresql://test/db", log_level="WARNING")

    assert settings.database_url == "postgresql://test/db"
    assert settings.log_level == "WARNING"


def test_missing_required_setting_fails_with_clear_message():
    with pytest.raises(ValidationError, match="database_url"):
        Settings()


def test_dotenv_file_is_loaded(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("KANON_DATABASE_URL=postgresql://from/dotenv\n")

    assert Settings().database_url == "postgresql://from/dotenv"
