from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("")
async def list_sinks(request: Request) -> dict:
    runtime = request.app.state.runtime
    pipeline = runtime.pipeline
    if pipeline is None:
        return {"sinks": []}
    sinks = pipeline.sinks
    return {
        "sinks": [{"name": s.name, "type": type(s).__name__, "config": s.config} for s in sinks]
    }
