from __future__ import annotations

from pathlib import Path

import uvicorn

from daena.api.server import DaenaAPI
from daena.config import load_config
from daena.logutil import get_logger, setup_logging

log = get_logger("daena.app")


def serve() -> None:
    """Entry point for `daena-serve` (systemd/uvicorn mode)."""
    config_path = _resolve_config_path()
    config = load_config(config_path)
    setup_logging(
        level=config.logging.level,
        fmt=config.logging.format,
        log_file=config.logging.file,
    )

    runtime = _build_runtime(config)
    api = DaenaAPI(runtime)
    app = api.build()

    log.info(
        "starting_server",
        host=config.api.http.host,
        port=config.api.http.port,
    )
    uvicorn.run(
        app,
        host=config.api.http.host,
        port=config.api.http.port,
        workers=config.api.http.workers,
        log_level=config.logging.level,
    )


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


def _build_runtime(config):
    """Lazy import to prevent premature backend init."""
    from daena.core.runtime import DaenaRuntime

    return DaenaRuntime(config)


if __name__ == "__main__":
    serve()
