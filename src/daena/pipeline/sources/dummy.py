from __future__ import annotations

import asyncio
import contextlib
from typing import Any

from daena.pipeline.base import Source
from daena.pipeline.record import Record


class DummySource(Source):
    """Generates test records at a configurable interval.

    Useful for development, testing, and demo purposes.
    """

    def __init__(self, name: str, config: dict[str, Any] | None = None) -> None:
        super().__init__(name, config)
        self._interval: float = float(config.get("interval", 5.0) if config else 5.0)
        self._message: str = (
            config.get("message", "daena test event") if config else "daena test event"
        )
        self._task: asyncio.Task[None] | None = None
        self._running = False
        self._on_record: callable | None = None

    def set_callback(self, cb: callable) -> None:
        self._on_record = cb

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._emit_loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    async def _emit_loop(self) -> None:
        counter = 0
        while self._running:
            counter += 1
            record = Record(
                source=self.name,
                record_type="test",
                body={
                    "message": f"{self._message} #{counter}",
                    "counter": counter,
                },
                metadata={"dummy": True},
            )
            if self._on_record:
                await self._on_record(record)
            await asyncio.sleep(self._interval)
