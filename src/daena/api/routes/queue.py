from __future__ import annotations

from fastapi import APIRouter, Query, Request

from daena.persistence.models import RecordState

router = APIRouter()


@router.get("")
async def get_queue_state(request: Request) -> dict:
    runtime = request.app.state.runtime
    backend = runtime.backend
    if backend is None:
        return {"error": "backend not initialized"}
    return {
        "pending": backend.count(RecordState.pending),
        "delivered": backend.count(RecordState.delivered),
        "failed": backend.count(RecordState.failed),
        "dead": backend.count(RecordState.dead),
        "total": backend.count(),
    }


@router.get("/pending")
async def get_pending(
    request: Request,
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
) -> dict:
    runtime = request.app.state.runtime
    backend = runtime.backend
    if backend is None:
        return {"error": "backend not initialized", "records": []}
    records = backend.list_by_state(RecordState.pending, limit=limit, offset=offset)
    return {"records": [r.to_dict() for r in records], "count": len(records)}


@router.get("/dead")
async def get_dead(
    request: Request,
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
) -> dict:
    runtime = request.app.state.runtime
    backend = runtime.backend
    if backend is None:
        return {"error": "backend not initialized", "records": []}
    records = backend.list_by_state(RecordState.dead, limit=limit, offset=offset)
    return {"records": [r.to_dict() for r in records], "count": len(records)}
