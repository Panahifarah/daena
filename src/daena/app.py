from __future__ import annotations

import asyncio
from pathlib import Path

from daena.api.grpc_server import DaenaGRPCServer
from daena.config import load_config
from daena.core.runtime import DaenaRuntime
from daena.logutil import get_logger, setup_logging

log = get_logger("daena.app")


def _resolve_config_path() -> str | None:
    for candidate in (
        "/etc/daena/daena.yaml",
        "./daena.yaml",
        "./config/daena.yaml",
    ):
        p = Path(candidate)
        if p.exists():
            return str(p)
    return None


def serve() -> None:
    """Entry point for `daena-serve` (systemd/gRPC mode)."""
    config_path = _resolve_config_path()
    config = load_config(config_path)
    setup_logging(
        level=config.logging.level,
        fmt=config.logging.format,
        log_file=config.logging.file,
    )

    runtime = DaenaRuntime(config)

    server = DaenaGRPCServer(
        runtime,
        host=config.api.grpc.host,
        port=config.api.grpc.port,
    )

    async def run() -> None:
        await runtime.start()
        await server.start()
        log.info(
            "grpc_server_serving",
            address=f"{config.api.grpc.host}:{config.api.grpc.port}",
        )
        try:
            await server.serve_forever()
        except asyncio.CancelledError:
            pass
        finally:
            await server.stop()
            await runtime.stop()

    asyncio.run(run())


if __name__ == "__main__":
    serve()
