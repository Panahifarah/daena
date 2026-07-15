from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable
from typing import Any

from daena.config import DaenaConfig
from daena.logutil import get_logger
from daena.persistence.backend import Backend
from daena.persistence.models import StoredRecord
from daena.pipeline.base import DeliveryResult, Processor, Sink, Source
from daena.pipeline.record import Record
from daena.plugins.registry import PluginRegistry

log = get_logger("daena.pipeline")


class SourceRunner:
    """Wraps a Source and handles record ingestion into the pipeline."""

    def __init__(
        self,
        source: Source,
        on_record: Callable[[Record], Any],
    ) -> None:
        self._source = source
        self._on_record = on_record

    async def start(self) -> None:
        if hasattr(self._source, "set_callback"):
            self._source.set_callback(self._on_record)
        log.info("source_starting", source=self._source.name)
        await self._source.start()

    async def stop(self) -> None:
        log.info("source_stopping", source=self._source.name)
        await self._source.stop()


class SinkDispatcher:
    """Manages delivery of records to a sink with retry logic."""

    def __init__(
        self,
        sink: Sink,
        backend: Backend,
        config: DaenaConfig,
    ) -> None:
        self._sink = sink
        self._backend = backend
        self._config = config
        self._logger = log.bind(sink=sink.name)

    async def start(self) -> None:
        self._logger.info("sink_starting")
        await self._sink.start()

    async def stop(self) -> None:
        self._logger.info("sink_stopping")
        await self._sink.stop()

    async def deliver(self, record: Record) -> DeliveryResult:
        return await self._sink.deliver(record)


class Pipeline:
    """Orchestrates the full collection → persist → forward data flow.

    Lifecycle:
      1. Sources emit Records
      2. Processors transform/filter Records
      3. Records are persisted to the backend
      4. SinkDispatcher reads pending records and delivers them
      5. Delivery results update record state (ack/nack/dead)
    """

    def __init__(
        self,
        config: DaenaConfig,
        backend: Backend,
        registry: PluginRegistry,
    ) -> None:
        self._config = config
        self._backend = backend
        self._registry = registry
        self._sources: list[Source] = []
        self._processors: list[Processor] = []
        self._dispatchers: list[SinkDispatcher] = []
        self._source_runners: list[SourceRunner] = []
        self._dispatch_task: asyncio.Task[None] | None = None
        self._running = False
        self._queue: asyncio.Queue[Record] = asyncio.Queue(maxsize=config.pipeline.max_queue_size)

    async def start(self) -> None:
        self._running = True
        self._build_pipeline()
        for runner in self._source_runners:
            await runner.start()
        for dispatcher in self._dispatchers:
            await dispatcher.start()
        self._dispatch_task = asyncio.create_task(self._dispatch_loop())
        log.info(
            "pipeline_started",
            sources=len(self._source_runners),
            sinks=len(self._dispatchers),
            processors=len(self._processors),
        )

    async def stop(self) -> None:
        self._running = False
        if self._dispatch_task:
            self._dispatch_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._dispatch_task
        for dispatcher in self._dispatchers:
            await dispatcher.stop()
        for runner in reversed(self._source_runners):
            await runner.stop()
        log.info("pipeline_stopped")

    def _build_pipeline(self) -> None:
        for sc in self._config.sources:
            cls = self._registry.get_source(sc.type)
            if not cls:
                log.warning("source_type_not_found", type=sc.type)
                continue
            source = cls(name=sc.name, config=sc.options)
            self._sources.append(source)
            runner = SourceRunner(source, self._ingest)
            self._source_runners.append(runner)

        for pc in self._config.processors:
            cls = self._registry.get_processor(pc.type)
            if not cls:
                log.warning("processor_type_not_found", type=pc.type)
                continue
            proc = cls(name=pc.name, config=pc.options)
            self._processors.append(proc)

        for sc in self._config.sinks:
            cls = self._registry.get_sink(sc.type)
            if not cls:
                log.warning("sink_type_not_found", type=sc.type)
                continue
            sink = cls(name=sc.name, config=sc.options)
            self._dispatchers.append(SinkDispatcher(sink, self._backend, self._config))

    async def _ingest(self, record: Record) -> None:
        """Called by sources. Runs processors and persists."""
        for proc in self._processors:
            result = await proc.process(record)
            if result is None:
                return
            record = result

        stored = StoredRecord(
            record_id=record.record_id,
            source=record.source,
            record_type=record.record_type,
            body=record.body,
            metadata=record.metadata,
            destination=record.destination,
            created_at=record.timestamp,
        )
        self._backend.put(stored)
        log.debug("record_persisted", record_id=record.record_id)

    async def _dispatch_loop(self) -> None:
        """Background loop: pull pending records from backend and deliver."""
        while self._running:
            try:
                await self._dispatch_batch()
            except asyncio.CancelledError:
                break
            except Exception:
                log.exception("dispatch_loop_error")
                await asyncio.sleep(1)

    async def _dispatch_batch(self) -> None:
        pending = self._backend.pending(limit=self._config.pipeline.batch_size)
        retry = self._backend.ready_for_retry(limit=self._config.pipeline.batch_size)
        records = pending + retry

        if not records:
            await asyncio.sleep(self._config.pipeline.flush_interval)
            return

        for stored in records:
            if not self._running:
                break
            record = Record(
                source=stored.source,
                record_type=stored.record_type,
                body=stored.body,
                metadata=stored.metadata,
                destination=stored.destination,
                record_id=stored.record_id,
                timestamp=stored.created_at,
            )
            for dispatcher in self._dispatchers:
                await self._deliver_with_retry(dispatcher, record)

        if len(records) < self._config.pipeline.batch_size:
            await asyncio.sleep(self._config.pipeline.flush_interval)

    async def _deliver_with_retry(self, dispatcher: SinkDispatcher, record: Record) -> None:
        retry_cfg = None
        for sc in self._config.sinks:
            if sc.name == dispatcher._sink.name:
                retry_cfg = sc.retry
                break

        max_attempts = retry_cfg.max_attempts if retry_cfg else 3
        min_delay = retry_cfg.min_delay if retry_cfg else 1.0
        max_delay = retry_cfg.max_delay if retry_cfg else 120.0

        attempt = 0
        while attempt < max_attempts:
            attempt += 1
            try:
                result = await dispatcher.deliver(record)
            except Exception as exc:
                result = DeliveryResult(
                    success=False,
                    record_id=record.record_id,
                    error=str(exc),
                )

            if result.success:
                self._backend.ack(record.record_id)
                return

            if result.permanent:
                self._backend.dead(record.record_id, result.error or "permanent failure")
                return

            backoff = min(min_delay * (2 ** (attempt - 1)), max_delay)
            stored = self._backend.get(record.record_id)
            if stored:
                self._backend.nack(
                    record.record_id,
                    error=result.error or "unknown",
                    retry_delay=backoff,
                )

            if attempt < max_attempts:
                await asyncio.sleep(backoff)

        self._backend.dead(
            record.record_id,
            f"max retries ({max_attempts}) exceeded: {result.error}",
        )

    @property
    def sources(self) -> list[Source]:
        return list(self._sources)

    @property
    def sinks(self) -> list[Sink]:
        return [d._sink for d in self._dispatchers]

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()
