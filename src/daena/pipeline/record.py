from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class Record:
    """In-memory representation of a collected event or log."""

    source: str
    record_type: str
    body: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)
    destination: str | None = None
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
