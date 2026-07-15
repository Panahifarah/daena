from __future__ import annotations

from fastapi import APIRouter, Request

from daena.core.runtime import DaenaRuntime

router = APIRouter()


def _resolve_runtime(request: Request) -> DaenaRuntime:
    return request.app.state.runtime  # type: ignore[no-any-return]


@router.get("/status")
async def get_status(request: Request) -> dict:
    runtime = _resolve_runtime(request)
    return {
        "service": "daena",
        "version": "0.1.0",
        "running": runtime._running,
        "uptime": None,
    }


@router.get("/health")
async def get_health(request: Request) -> dict:
    runtime = _resolve_runtime(request)
    healthy = runtime._running
    return {
        "healthy": healthy,
        "running": runtime._running,
        "backend": runtime.backend is not None,
        "plugins_loaded": bool(runtime.registry.list_sources()),
    }


@router.get("/config")
async def get_config(request: Request) -> dict:
    runtime = _resolve_runtime(request)
    cfg = runtime.config
    return {
        "data_dir": cfg.data_dir,
        "log_dir": cfg.log_dir,
        "api": cfg.api.model_dump(),
        "pipeline": cfg.pipeline.model_dump(),
        "persistence": cfg.persistence.model_dump(),
        "sources": [s.model_dump() for s in cfg.sources],
        "processors": [p.model_dump() for p in cfg.processors],
        "sinks": [s.model_dump() for s in cfg.sinks],
    }
