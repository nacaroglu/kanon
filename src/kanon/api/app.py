from fastapi import FastAPI

from kanon import __version__
from kanon.api import health
from kanon.settings import get_settings


def create_app() -> FastAPI:
    get_settings()  # fail fast at startup if required settings are missing
    app = FastAPI(title="Kanon", version=__version__)
    app.include_router(health.router)
    return app
