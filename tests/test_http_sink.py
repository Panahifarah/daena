"""End-to-end test for HTTP sink data forwarding."""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from daena.config import DaenaConfig, SinkConfig, SourceConfig
from daena.core.runtime import DaenaRuntime
from daena.logutil import setup_logging
from daena.persistence.models import RecordState

setup_logging(level="error", fmt="json")

pytestmark = pytest.mark.asyncio


class _TestHTTPServer:
    """Minimal async HTTP server to receive forwarded records."""

    def __init__(self, status: int = 200, body: str = "OK") -> None:
        self.received: list[dict[str, Any]] = []
        self._status = status
        self._body = body
        self._server: asyncio.AbstractServer | None = None

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        data = await reader.readuntil(b"\r\n\r\n")
        raw = data.decode()
        content_length = 0
        for line in raw.split("\r\n"):
            if line.lower().startswith("content-length:"):
                content_length = int(line.split(":")[1].strip())
        if content_length:
            body = await reader.readexactly(content_length)
            try:
                payload = json.loads(body)
                self.received.append(payload)
            except json.JSONDecodeError:
                pass
        resp_body = self._body.encode()
        writer.write(
            f"HTTP/1.1 {self._status} OK\r\nContent-Length: {len(resp_body)}\r\n\r\n".encode()
            + resp_body
        )
        await writer.drain()
        writer.close()

    async def start(self, host: str = "127.0.0.1", port: int = 0) -> int:
        self._server = await asyncio.start_server(self._handle, host, port)
        addr = self._server.sockets[0].getsockname()
        return addr[1]

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()


async def test_http_sink_forwards_records() -> None:
    server = _TestHTTPServer(status=200)
    port = await server.start()

    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir) / "data"
        data_dir.mkdir(parents=True)

        config = DaenaConfig()
        config.data_dir = str(tmpdir)
        config.log_dir = str(tmpdir)
        config.persistence.lmdb.path = str(data_dir / "lmdb")
        config.sources = [
            SourceConfig(
                name="test_source",
                type="dummy",
                options={"interval": 0.2, "message": "http_sink_test"},
            )
        ]
        config.sinks = [
            SinkConfig(
                name="test_sink",
                type="http",
                options={"url": f"http://127.0.0.1:{port}/ingest", "timeout": 5.0},
            )
        ]

        runtime = DaenaRuntime(config)
        await runtime.start()
        await asyncio.sleep(3.0)
        await runtime.stop()

    await server.stop()

    assert len(server.received) > 0, f"Expected at least 1 record, got {len(server.received)}"

    first = server.received[0]
    assert "id" in first
    assert "source" in first
    assert first["source"] == "test_source"
    assert "body" in first
    assert "timestamp" in first


async def test_http_sink_permanent_failure_on_404() -> None:
    """4xx errors (non-429) should permanently fail the record."""
    server = _TestHTTPServer(status=404, body="Not Found")
    port = await server.start()

    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir) / "data"
        data_dir.mkdir(parents=True)

        config = DaenaConfig()
        config.data_dir = str(tmpdir)
        config.log_dir = str(tmpdir)
        config.persistence.lmdb.path = str(data_dir / "lmdb")
        config.sources = [
            SourceConfig(
                name="test_source",
                type="dummy",
                options={"interval": 0.2, "message": "http_404_test"},
            )
        ]
        config.sinks = [
            SinkConfig(
                name="test_sink",
                type="http",
                options={
                    "url": f"http://127.0.0.1:{port}/ingest",
                    "timeout": 5.0,
                    "retry": {"max_attempts": 1, "min_delay": 0.1},
                },
            )
        ]

        runtime = DaenaRuntime(config)
        await runtime.start()
        await asyncio.sleep(3.0)

        dead = runtime.backend.count(RecordState.dead)
        failed = runtime.backend.count(RecordState.failed)
        total = runtime.backend.count()

        await runtime.stop()

    await server.stop()

    assert dead > 0 or failed > 0, (
        f"Expected records to fail, dead={dead} failed={failed} total={total}"
    )


async def test_http_sink_delivery_result() -> None:
    """Successful HTTP delivery should create delivered records."""
    server = _TestHTTPServer(status=200)
    port = await server.start()

    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir) / "data"
        data_dir.mkdir(parents=True)

        config = DaenaConfig()
        config.data_dir = str(tmpdir)
        config.log_dir = str(tmpdir)
        config.persistence.lmdb.path = str(data_dir / "lmdb")
        config.sources = [
            SourceConfig(
                name="test_source",
                type="dummy",
                options={"interval": 0.2, "message": "http_delivery_test"},
            )
        ]
        config.sinks = [
            SinkConfig(
                name="test_sink",
                type="http",
                options={"url": f"http://127.0.0.1:{port}/ingest", "timeout": 5.0},
            )
        ]

        runtime = DaenaRuntime(config)
        await runtime.start()
        await asyncio.sleep(3.0)

        delivered = runtime.backend.count(RecordState.delivered)
        await runtime.stop()

    await server.stop()

    assert delivered > 0, f"Expected delivered records, got {delivered}"
