from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """The only place configuration is read from the environment / `.env`."""

    model_config = SettingsConfigDict(env_prefix="KANON_", env_file=".env", extra="ignore")

    database_url: str
    log_level: str = "INFO"
    # Directory holding the approved procedure repository. Only its existence is checked
    # here; whether it is a Git repository is checked when the repository is opened.
    procedure_repo_path: Path | None = None

    @field_validator("procedure_repo_path")
    @classmethod
    def _procedure_repo_path_must_exist(cls, value: Path | None) -> Path | None:
        if value is None:
            return None
        value = value.expanduser()
        if not value.exists():
            raise ValueError(f"procedure repository path does not exist: {value}")
        if not value.is_dir():
            raise ValueError(f"procedure repository path is not a directory: {value}")
        return value


@lru_cache
def get_settings() -> Settings:
    """FastAPI dependency; override via `app.dependency_overrides[get_settings]`."""
    return Settings()  # type: ignore[call-arg]  # required fields come from the environment
