"""End-to-end smoke test: gRPC server + pipeline + CLI commands."""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path

import grpc.aio

from daena.api.grpc_server import DaenaGRPCServer
from daena.api.pb2 import daena_pb2 as pb2
from daena.api.pb2 import daena_pb2_grpc as pb2_grpc
from daena.config import DaenaConfig, ProcessorConfig, SinkConfig, SourceConfig
from daena.core.runtime import DaenaRuntime
from daena.logutil import setup_logging

setup_logging(level="error", fmt="json")


async def smoke_test() -> int:
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir) / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        config = DaenaConfig()
        config.data_dir = str(data_dir)
        config.log_dir = str(tmpdir)
        config.persistence.lmdb.path = str(data_dir / "lmdb")
        config.sources = [
            SourceConfig(
                name="smoke_source",
                type="dummy",
                options={"interval": 0.5, "message": "smoke_test"},
            )
        ]
        config.processors = [
            ProcessorConfig(name="passthrough", type="passthrough"),
        ]
        config.sinks = [
            SinkConfig(name="log", type="dummy"),
        ]

        runtime = DaenaRuntime(config)
        server = DaenaGRPCServer(runtime, host="127.0.0.1", port=18642)

        await runtime.start()
        await server.start()

        channel = grpc.aio.insecure_channel("127.0.0.1:18642")
        stub = pb2_grpc.DaenaStub(channel)

        await asyncio.sleep(2.5)

        failed = 0

        # 1. GetStatus
        try:
            resp = await stub.GetStatus(pb2.Empty(), timeout=5)
            assert resp.service == "daena"
            assert resp.version == "0.1.0"
            assert resp.running is True
            print(f"[PASS] GetStatus: service={resp.service}, running={resp.running}")
        except Exception as e:
            print(f"[FAIL] GetStatus: {e}")
            failed += 1

        # 2. GetHealth
        try:
            resp = await stub.GetHealth(pb2.Empty(), timeout=5)
            assert resp.healthy is True
            assert resp.running is True
            assert resp.backend is True
            assert resp.plugins_loaded is True
            print(f"[PASS] GetHealth: healthy={resp.healthy}, backend={resp.backend}")
        except Exception as e:
            print(f"[FAIL] GetHealth: {e}")
            failed += 1

        # 3. GetConfig
        try:
            resp = await stub.GetConfig(pb2.Empty(), timeout=5)
            cfg = json.loads(resp.config_json)
            assert "sources" in cfg
            assert cfg["sources"][0]["name"] == "smoke_source"
            print(f"[PASS] GetConfig: sources={len(cfg['sources'])}")
        except Exception as e:
            print(f"[FAIL] GetConfig: {e}")
            failed += 1

        # 4. ListPlugins
        try:
            resp = await stub.ListPlugins(pb2.Empty(), timeout=5)
            assert len(resp.sources.items) > 0
            assert len(resp.processors.items) > 0
            assert len(resp.sinks.items) > 0
            print(
                f"[PASS] ListPlugins: sources={len(resp.sources.items)}, "
                f"processors={len(resp.processors.items)}, sinks={len(resp.sinks.items)}"
            )
        except Exception as e:
            print(f"[FAIL] ListPlugins: {e}")
            failed += 1

        # 5. GetQueueState
        try:
            resp = await stub.GetQueueState(pb2.Empty(), timeout=5)
            print(
                f"[PASS] GetQueueState: pending={resp.pending}, "
                f"delivered={resp.delivered}, total={resp.total}"
            )
        except Exception as e:
            print(f"[FAIL] GetQueueState: {e}")
            failed += 1

        # 6. ListPendingRecords
        try:
            resp = await stub.ListPendingRecords(pb2.Empty(), timeout=5)
            print(f"[PASS] ListPendingRecords: count={resp.count}")
        except Exception as e:
            print(f"[FAIL] ListPendingRecords: {e}")
            failed += 1

        # 7. ListDeadRecords
        try:
            resp = await stub.ListDeadRecords(pb2.Empty(), timeout=5)
            print(f"[PASS] ListDeadRecords: count={resp.count}")
        except Exception as e:
            print(f"[FAIL] ListDeadRecords: {e}")
            failed += 1

        # 8. ListSinks
        try:
            resp = await stub.ListSinks(pb2.Empty(), timeout=5)
            assert len(resp.sinks) > 0
            assert resp.sinks[0].name == "log"
            print(f"[PASS] ListSinks: sinks={len(resp.sinks)}")
        except Exception as e:
            print(f"[FAIL] ListSinks: {e}")
            failed += 1

        # 9. Pipeline produced records
        total = runtime.backend.count()
        if total > 0:
            print(f"[PASS] Pipeline production: {total} records created in 2.5s")
        else:
            print("[FAIL] Pipeline production: no records produced")
            failed += 1

        # 10. ReloadConfig
        try:
            resp = await stub.ReloadConfig(pb2.Empty(), timeout=10)
            assert resp.success is True, f"Reload failed: {resp.message}"
            print("[PASS] ReloadConfig: success=True")
        except Exception as e:
            print(f"[FAIL] ReloadConfig: {e}")
            failed += 1

        await channel.close()
        await server.stop()
        await runtime.stop()

    print(f"\n{'=' * 40}")
    if failed:
        print(f"[RESULT] {failed} test(s) FAILED")
    else:
        print("[RESULT] All smoke tests PASSED")
    return failed


if __name__ == "__main__":
    ret = asyncio.run(smoke_test())
    sys.exit(ret)
