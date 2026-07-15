from __future__ import annotations

from daena.pipeline.base import DeliveryResult, Sink
from daena.pipeline.record import Record


class DummySink(Sink):
    """Logs delivered records without sending anywhere.

    Useful for testing and development.
    """

    async def deliver(self, record: Record) -> DeliveryResult:
        return DeliveryResult(success=True, record_id=record.record_id)
