from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from daena.pipeline.record import Record


@dataclass
class DeliveryResult:
    success: bool
    record_id: str
    error: str | None = None
    permanent: bool = False


class Source(ABC):
    """Base class for all record sources.

    Sources collect or receive data and push Records into the pipeline.
    """

    name: str

    def __init__(self, name: str, config: dict[str, Any] | None = None) -> None:
        self.name = name
        self.config = config or {}

    @abstractmethod
    async def start(self) -> None:
        """Start collecting records. Called during service startup."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop collecting. Called during shutdown."""


class Processor(ABC):
    """Base class for record processors.

    Processors transform, filter, or enrich Records passing through the pipeline.
    Return None to drop the record.
    """

    name: str

    def __init__(self, name: str, config: dict[str, Any] | None = None) -> None:
        self.name = name
        self.config = config or {}

    @abstractmethod
    async def process(self, record: Record) -> Record | None: ...


class Sink(ABC):
    """Base class for record sinks.

    Sinks deliver Records to external destinations.
    """

    name: str

    def __init__(self, name: str, config: dict[str, Any] | None = None) -> None:
        self.name = name
        self.config = config or {}

    @abstractmethod
    async def deliver(self, record: Record) -> DeliveryResult: ...

    async def start(self) -> None:
        return

    async def stop(self) -> None:
        return
