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


def test_procedure_repo_path_is_optional():
    assert Settings(database_url="postgresql://x/y").procedure_repo_path is None


def test_existing_procedure_repo_path_is_accepted(tmp_path):
    settings = Settings(database_url="postgresql://x/y", procedure_repo_path=tmp_path)

    assert settings.procedure_repo_path == tmp_path


def test_procedure_repo_path_is_read_from_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("KANON_DATABASE_URL", "postgresql://x/y")
    monkeypatch.setenv("KANON_PROCEDURE_REPO_PATH", str(tmp_path))

    assert Settings().procedure_repo_path == tmp_path


def test_missing_procedure_repo_path_fails_with_clear_message(tmp_path):
    missing = tmp_path / "nope"

    with pytest.raises(ValidationError, match="procedure repository path does not exist") as exc:
        Settings(database_url="postgresql://x/y", procedure_repo_path=missing)

    assert str(missing) in str(exc.value)


def test_procedure_repo_path_must_be_a_directory(tmp_path):
    file = tmp_path / "file.txt"
    file.write_text("x")

    with pytest.raises(ValidationError, match="is not a directory"):
        Settings(database_url="postgresql://x/y", procedure_repo_path=file)


def test_app_refuses_to_start_with_missing_procedure_repo(tmp_path, monkeypatch):
    from kanon.api.app import create_app

    monkeypatch.setenv("KANON_DATABASE_URL", "postgresql://x/y")
    monkeypatch.setenv("KANON_PROCEDURE_REPO_PATH", str(tmp_path / "nope"))

    with pytest.raises(ValidationError, match="does not exist"):
        create_app()
