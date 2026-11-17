import pytest

from kanon.settings import get_settings


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch, tmp_path):
    """Keep tests independent of the real environment and any local `.env`."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("KANON_DATABASE_URL", raising=False)
    monkeypatch.delenv("KANON_LOG_LEVEL", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
