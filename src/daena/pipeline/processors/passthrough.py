from __future__ import annotations

from daena.pipeline.base import Processor
from daena.pipeline.record import Record


class PassthroughProcessor(Processor):
    """Passes records through without modification."""

    async def process(self, record: Record) -> Record | None:
        return record
