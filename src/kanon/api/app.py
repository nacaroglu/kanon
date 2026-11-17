from fastapi import FastAPI

from kanon import __version__
from kanon.api import health


def create_app() -> FastAPI:
    app = FastAPI(title="Kanon", version=__version__)
    app.include_router(health.router)
    return app
