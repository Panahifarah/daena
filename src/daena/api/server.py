from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from daena.api.router import api_router
from daena.core.runtime import DaenaRuntime
from daena.logutil import get_logger

log = get_logger("daena.api")


class DaenaAPI:
    """Wraps the FastAPI application with daena runtime integration."""

    def __init__(self, runtime: DaenaRuntime) -> None:
        self._runtime = runtime
        self._app: FastAPI | None = None

    def build(self) -> FastAPI:
        runtime = self._runtime

        @asynccontextmanager
        async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
            log.info("api_starting")
            await runtime.start()
            yield
            log.info("api_stopping")
            await runtime.stop()

        app = FastAPI(
            title="Daena",
            description="Daena service management API",
            version="0.1.0",
            lifespan=lifespan,
        )

        app.state.runtime = runtime
        app.include_router(api_router, prefix="/api/v1")

        self._app = app
        return app

    @property
    def app(self) -> FastAPI:
        if self._app is None:
            return self.build()
        return self._app
