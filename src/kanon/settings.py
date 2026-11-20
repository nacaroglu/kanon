from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """The only place configuration is read from the environment / `.env`."""

    model_config = SettingsConfigDict(env_prefix="KANON_", env_file=".env", extra="ignore")

    database_url: str
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """FastAPI dependency; override via `app.dependency_overrides[get_settings]`."""
    return Settings()  # type: ignore[call-arg]  # required fields come from the environment
