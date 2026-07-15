from __future__ import annotations

import json

import grpc
import grpc.aio

from daena.api.pb2 import daena_pb2 as pb2
from daena.api.pb2 import daena_pb2_grpc as pb2_grpc
from daena.core.runtime import DaenaRuntime
from daena.logutil import get_logger
from daena.persistence.models import RecordState

log = get_logger("daena.grpc")


def _record_to_proto(record) -> pb2.RecordData:
    return pb2.RecordData(
        record_id=record.record_id,
        source=record.source,
        record_type=record.record_type,
        body=json.dumps(record.body),
        metadata=json.dumps(record.metadata),
        state=record.state.value if hasattr(record.state, "value") else record.state,
        created_at=record.created_at or "",
        updated_at=record.updated_at or "",
        retry_count=record.retry_count,
        next_retry_at=record.next_retry_at or "",
        last_error=record.last_error or "",
        destination=record.destination or "",
    )


# ruff: noqa: N802, ARG002
class DaenaServicer(pb2_grpc.DaenaServicer):
    def __init__(self, runtime: DaenaRuntime) -> None:
        self._runtime = runtime

    async def GetStatus(self, request, context):
        return pb2.StatusResponse(
            service="daena",
            version="0.1.0",
            running=self._runtime._running,
        )

    async def GetHealth(self, request, context):
        return pb2.HealthResponse(
            healthy=self._runtime._running,
            running=self._runtime._running,
            backend=self._runtime.backend is not None,
            plugins_loaded=bool(self._runtime.registry.list_sources()),
        )

    async def GetConfig(self, request, context):
        cfg = self._runtime.config
        raw = {
            "data_dir": cfg.data_dir,
            "log_dir": cfg.log_dir,
            "api": {"grpc": {"host": cfg.api.grpc.host, "port": cfg.api.grpc.port}},
            "pipeline": cfg.pipeline.model_dump(),
            "persistence": cfg.persistence.model_dump(),
            "sources": [s.model_dump() for s in cfg.sources],
            "processors": [p.model_dump() for p in cfg.processors],
            "sinks": [s.model_dump() for s in cfg.sinks],
        }
        return pb2.ConfigResponse(config_json=json.dumps(raw))

    async def ListPlugins(self, request, context):
        registry = self._runtime.registry
        all_plugins = registry.all_plugins()

        def _cat(key: str):
            items = all_plugins.get(key, {})
            return pb2.PluginCategory(
                items=[pb2.PluginInfo(name=n, class_name=cls.__name__) for n, cls in items.items()]
            )

        return pb2.PluginListResponse(
            sources=_cat("sources"),
            processors=_cat("processors"),
            sinks=_cat("sinks"),
        )

    async def GetQueueState(self, request, context):
        backend = self._runtime.backend
        if backend is None:
            return pb2.QueueStateResponse()
        return pb2.QueueStateResponse(
            pending=backend.count(RecordState.pending),
            delivered=backend.count(RecordState.delivered),
            failed=backend.count(RecordState.failed),
            dead=backend.count(RecordState.dead),
            total=backend.count(),
        )

    async def ListPendingRecords(self, request, context):
        backend = self._runtime.backend
        if backend is None:
            return pb2.RecordList(records=[], count=0)
        records = backend.list_by_state(
            RecordState.pending,
            limit=request.limit or 100,
            offset=request.offset or 0,
        )
        return pb2.RecordList(
            records=[_record_to_proto(r) for r in records],
            count=len(records),
        )

    async def ListDeadRecords(self, request, context):
        backend = self._runtime.backend
        if backend is None:
            return pb2.RecordList(records=[], count=0)
        records = backend.list_by_state(
            RecordState.dead,
            limit=request.limit or 100,
            offset=request.offset or 0,
        )
        return pb2.RecordList(
            records=[_record_to_proto(r) for r in records],
            count=len(records),
        )

    async def ListSinks(self, request, context):
        pipeline = self._runtime.pipeline
        if pipeline is None:
            return pb2.SinkList(sinks=[])
        return pb2.SinkList(
            sinks=[pb2.SinkInfo(name=s.name, type=type(s).__name__) for s in pipeline.sinks]
        )

    async def ReloadConfig(self, request, context):
        try:
            await self._runtime.reload()
            return pb2.ReloadResponse(success=True, message="Configuration reloaded")
        except Exception as exc:
            return pb2.ReloadResponse(success=False, message=str(exc))


class DaenaGRPCServer:
    """Manages the gRPC server lifecycle."""

    def __init__(self, runtime: DaenaRuntime, host: str = "127.0.0.1", port: int = 8642) -> None:
        self._runtime = runtime
        self._host = host
        self._port = port
        self._server: grpc.aio.Server | None = None

    async def start(self) -> None:
        self._server = grpc.aio.server()
        servicer = DaenaServicer(self._runtime)
        pb2_grpc.add_DaenaServicer_to_server(servicer, self._server)
        address = f"{self._host}:{self._port}"
        self._server.add_insecure_port(address)
        await self._server.start()
        log.info("grpc_server_started", address=address)

    async def stop(self) -> None:
        if self._server:
            await self._server.stop(grace=5)
            log.info("grpc_server_stopped")

    async def serve_forever(self) -> None:
        if self._server:
            await self._server.wait_for_termination()
