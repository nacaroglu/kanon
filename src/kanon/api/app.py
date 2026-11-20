import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

from kanon import __version__
from kanon.api import health
from kanon.logging import configure_logging
from kanon.settings import get_settings

request_logger = logging.getLogger("kanon.request")


def create_app() -> FastAPI:
    settings = get_settings()  # fail fast at startup if required settings are missing
    configure_logging(settings.log_level)

    app = FastAPI(title="Kanon", version=__version__)

    @app.middleware("http")
    async def log_requests(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            request_logger.info(
                "request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": status,
                    "duration_ms": round((time.perf_counter() - start) * 1000, 2),
                },
            )

    app.include_router(health.router)
    return app
