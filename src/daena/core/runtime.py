from __future__ import annotations

from daena.config import DaenaConfig
from daena.core.pipeline import Pipeline
from daena.logutil import get_logger
from daena.persistence.backend import Backend
from daena.persistence.lmdb import LMDBBackend
from daena.plugins.loader import discover_plugins
from daena.plugins.registry import PluginRegistry, get_registry

log = get_logger("daena.runtime")


class DaenaRuntime:
    """Top-level service runtime.

    Owns configuration, persistence backend, pipeline, and lifecycle.
    Designed to run under asyncio with clean signal-based shutdown.
    """

    def __init__(self, config: DaenaConfig) -> None:
        self._config = config
        self._registry = get_registry()
        self._backend: Backend | None = None
        self._pipeline: Pipeline | None = None
        self._running = False

    @property
    def config(self) -> DaenaConfig:
        return self._config

    @property
    def registry(self) -> PluginRegistry:
        return self._registry

    @property
    def backend(self) -> Backend | None:
        return self._backend

    @property
    def pipeline(self) -> Pipeline | None:
        return self._pipeline

    async def start(self) -> None:
        log.info("runtime_starting")

        discover_plugins()
        log.info(
            "plugins_discovered",
            sources=list(self._registry.list_sources().keys()),
            processors=list(self._registry.list_processors().keys()),
            sinks=list(self._registry.list_sinks().keys()),
        )

        persistence_cfg = self._config.persistence
        if persistence_cfg.backend == "lmdb":
            self._backend = LMDBBackend(
                path=persistence_cfg.lmdb.path,
                map_size=persistence_cfg.lmdb.map_size,
                max_databases=persistence_cfg.lmdb.max_databases,
            )
        else:
            raise ValueError(f"Unknown backend: {persistence_cfg.backend}")

        self._backend.open()
        log.info("backend_opened", backend=persistence_cfg.backend)

        self._pipeline = Pipeline(self._config, self._backend, self._registry)
        await self._pipeline.start()
        self._running = True
        log.info("runtime_started")

    async def stop(self) -> None:
        log.info("runtime_stopping")
        self._running = False

        if self._pipeline:
            await self._pipeline.stop()

        if self._backend:
            self._backend.close()
            log.info("backend_closed")

        log.info("runtime_stopped")

    async def reload(self) -> None:
        log.info("runtime_reloading")
        await self.stop()
        await self.start()
        log.info("runtime_reloaded")
