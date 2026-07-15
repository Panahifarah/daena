from __future__ import annotations

import pytest

from daena.pipeline.base import DeliveryResult, Processor
from daena.pipeline.processors.passthrough import PassthroughProcessor
from daena.pipeline.record import Record
from daena.pipeline.sinks.dummy import DummySink
from daena.pipeline.sinks.http import HTTPSink
from daena.pipeline.sources.dummy import DummySource


def test_dummy_source_config() -> None:
    source = DummySource(
        name="test",
        config={"interval": 1.0, "message": "hello"},
    )
    assert source.name == "test"
    assert source._interval == 1.0
    assert source._message == "hello"


@pytest.mark.asyncio
async def test_dummy_sink_delivery() -> None:
    sink = DummySink(name="test")
    record = Record(source="test", record_type="test", body={"key": "value"})
    result = await sink.deliver(record)
    assert isinstance(result, DeliveryResult)
    assert result.success is True
    assert result.record_id == record.record_id


@pytest.mark.asyncio
async def test_passthrough_processor() -> None:
    proc = PassthroughProcessor(name="test")
    record = Record(source="test", record_type="test", body={"key": "value"})
    result = await proc.process(record)
    assert result is not None
    assert result.record_id == record.record_id
    assert result.body == {"key": "value"}


def test_http_sink_requires_url() -> None:
    sink = HTTPSink(name="test", config={"url": "http://example.com/ingest"})
    assert sink._url == "http://example.com/ingest"
    assert sink._method == "POST"


def test_record_has_id() -> None:
    r1 = Record(source="s1", record_type="t1", body={})
    r2 = Record(source="s2", record_type="t2", body={})
    assert r1.record_id != r2.record_id
    assert r1.timestamp is not None


@pytest.mark.asyncio
async def test_processor_drop_record() -> None:
    class DropProcessor(Processor):
        async def process(self, record: Record) -> Record | None:  # noqa: ARG002
            return None

    proc = DropProcessor(name="dropper")
    record = Record(source="test", record_type="test", body={})
    result = await proc.process(record)
    assert result is None
