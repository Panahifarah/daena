from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class RecordState(StrEnum):
    pending = "pending"
    delivering = "delivering"
    delivered = "delivered"
    failed = "failed"
    dead = "dead"


class StoredRecord:
    """A record as stored in the persistence backend."""

    def __init__(
        self,
        record_id: str | None = None,
        source: str = "",
        record_type: str = "",
        body: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        state: RecordState = RecordState.pending,
        created_at: str | None = None,
        updated_at: str | None = None,
        retry_count: int = 0,
        next_retry_at: str | None = None,
        last_error: str | None = None,
        destination: str | None = None,
    ) -> None:
        self.record_id = record_id or str(uuid.uuid4())
        self.source = source
        self.record_type = record_type
        self.body = body or {}
        self.metadata = metadata or {}
        self.state = state
        self.created_at = created_at or datetime.now(UTC).isoformat()
        self.updated_at = updated_at or self.created_at
        self.retry_count = retry_count
        self.next_retry_at = next_retry_at
        self.last_error = last_error
        self.destination = destination

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "source": self.source,
            "record_type": self.record_type,
            "body": self.body,
            "metadata": self.metadata,
            "state": self.state.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "retry_count": self.retry_count,
            "next_retry_at": self.next_retry_at,
            "last_error": self.last_error,
            "destination": self.destination,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StoredRecord:
        return cls(
            record_id=data.get("record_id"),
            source=data.get("source", ""),
            record_type=data.get("record_type", ""),
            body=data.get("body", {}),
            metadata=data.get("metadata", {}),
            state=RecordState(data.get("state", "pending")),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            retry_count=data.get("retry_count", 0),
            next_retry_at=data.get("next_retry_at"),
            last_error=data.get("last_error"),
            destination=data.get("destination"),
        )
