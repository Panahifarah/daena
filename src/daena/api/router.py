from __future__ import annotations

from fastapi import APIRouter

from daena.api.routes.plugins import router as plugins_router
from daena.api.routes.queue import router as queue_router
from daena.api.routes.sinks import router as sinks_router
from daena.api.routes.system import router as system_router

api_router = APIRouter()

api_router.include_router(system_router, prefix="/system", tags=["system"])
api_router.include_router(plugins_router, prefix="/plugins", tags=["plugins"])
api_router.include_router(queue_router, prefix="/queue", tags=["queue"])
api_router.include_router(sinks_router, prefix="/sinks", tags=["sinks"])
