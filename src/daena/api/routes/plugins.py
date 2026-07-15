from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("")
async def list_plugins(request: Request) -> dict:
    runtime = request.app.state.runtime
    registry = runtime.registry
    plugins = registry.all_plugins()
    result: dict[str, list[dict]] = {}
    for category, entries in plugins.items():
        result[category] = [{"name": name, "class": cls.__name__} for name, cls in entries.items()]
    return {"plugins": result}
