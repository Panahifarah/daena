from __future__ import annotations

import asyncio

import grpc  # noqa: I001
import pytest

from daena.api.grpc_server import DaenaGRPCServer
from daena.api.pb2 import daena_pb2 as pb2
from daena.api.pb2 import daena_pb2_grpc as pb2_grpc
from daena.config import DaenaConfig, SinkConfig, SourceConfig
from daena.core.runtime import DaenaRuntime


@pytest.fixture
async def grpc_env():
    config = DaenaConfig()
    config.sources = [
        SourceConfig(name="dummy", type="dummy", options={"interval": 0.2, "message": "test"})
    ]
    config.sinks = [SinkConfig(name="log", type="dummy")]
    config.persistence.lmdb.path = "/tmp/daena_grpc_test"
    config.api.grpc.port = 18642

    runtime = DaenaRuntime(config)
    await runtime.start()

    server = DaenaGRPCServer(runtime, host="127.0.0.1", port=18642)
    await server.start()

    channel = grpc.aio.insecure_channel("127.0.0.1:18642")
    stub = pb2_grpc.DaenaStub(channel)

    yield runtime, stub, server

    await channel.close()
    await server.stop()
    await runtime.stop()


@pytest.mark.asyncio
async def test_get_status(grpc_env) -> None:
    _, stub, _ = grpc_env
    resp = await stub.GetStatus(pb2.Empty(), timeout=5)
    assert resp.service == "daena"
    assert resp.version == "0.1.0"
    assert resp.running is True


@pytest.mark.asyncio
async def test_get_health(grpc_env) -> None:
    _, stub, _ = grpc_env
    resp = await stub.GetHealth(pb2.Empty(), timeout=5)
    assert resp.healthy is True
    assert resp.running is True


@pytest.mark.asyncio
async def test_get_config(grpc_env) -> None:
    _, stub, _ = grpc_env
    resp = await stub.GetConfig(pb2.Empty(), timeout=5)
    assert resp.config_json != ""


@pytest.mark.asyncio
async def test_list_plugins(grpc_env) -> None:
    _, stub, _ = grpc_env
    resp = await stub.ListPlugins(pb2.Empty(), timeout=5)
    assert len(resp.sources.items) > 0
    assert len(resp.sinks.items) > 0


@pytest.mark.asyncio
async def test_get_queue_state(grpc_env) -> None:
    _, stub, _ = grpc_env
    await asyncio.sleep(1)
    resp = await stub.GetQueueState(pb2.Empty(), timeout=5)
    assert resp.total > 0
    assert resp.pending > 0


@pytest.mark.asyncio
async def test_list_pending_records(grpc_env) -> None:
    runtime, stub, _ = grpc_env
    await asyncio.sleep(1)
    req = pb2.Pagination(limit=10, offset=0)
    resp = await stub.ListPendingRecords(req, timeout=5)
    assert resp.count > 0
    assert len(resp.records) > 0
    assert resp.records[0].record_id != ""


@pytest.mark.asyncio
async def test_list_sinks(grpc_env) -> None:
    _, stub, _ = grpc_env
    resp = await stub.ListSinks(pb2.Empty(), timeout=5)
    assert len(resp.sinks) >= 1
    assert resp.sinks[0].name == "log"


@pytest.mark.asyncio
async def test_reload_config(grpc_env) -> None:
    _, stub, _ = grpc_env
    resp = await stub.ReloadConfig(pb2.Empty(), timeout=10)
    assert resp.success is True
