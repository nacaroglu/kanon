from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """The only place configuration is read from the environment / `.env`."""

    model_config = SettingsConfigDict(env_prefix="KANON_", env_file=".env", extra="ignore")

    database_url: str
    log_level: str = "INFO"
    # Directory holding the approved procedure repository. Only its existence is checked
    # here; whether it is a Git repository is checked when the repository is opened.
    procedure_repo_path: Path | None = None

    # The language model endpoint (OpenAI-compatible, ADR-003). All three are needed to make a
    # call; the application starts without them and fails only when a model is first used.
    llm_base_url: str | None = None
    llm_api_key: SecretStr | None = None  # a secret: masked in repr, never logged
    llm_model: str | None = None
    llm_timeout_seconds: float = Field(default=60.0, gt=0)

    @field_validator("llm_base_url", "llm_api_key", "llm_model", mode="before")
    @classmethod
    def _blank_means_unset(cls, value: object) -> object:
        # Docker Compose passes unset variables through as empty strings.
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("llm_base_url")
    @classmethod
    def _llm_base_url_must_be_http(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith(("http://", "https://")):
            raise ValueError("llm_base_url must start with http:// or https://")
        return value

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
