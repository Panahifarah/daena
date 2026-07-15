from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from daena.persistence.models import RecordState, StoredRecord


class Backend(Protocol):
    """Abstract interface for persistence backends.

    This Protocol defines the contract that all storage backends must fulfill.
    The MVP implementation uses LMDB; future implementations may target
    NATS JetStream, filesystem-backed stores, or cloud queues.
    """

    def open(self) -> None:
        """Open or initialize the backend."""

    def close(self) -> None:
        """Close the backend and release resources."""

    def put(self, record: StoredRecord) -> None:
        """Store a new record."""

    def get(self, record_id: str) -> StoredRecord | None:
        """Retrieve a record by ID."""

    def update_state(
        self,
        record_id: str,
        state: RecordState,
        last_error: str | None = None,
        next_retry_at: str | None = None,
    ) -> None:
        """Update a record's delivery state."""

    def pending(
        self,
        limit: int = 100,
        older_than: str | None = None,
    ) -> list[StoredRecord]:
        """Return pending records for delivery, oldest first."""

    def ready_for_retry(
        self,
        limit: int = 100,
        now: str | None = None,
    ) -> list[StoredRecord]:
        """Return failed records whose retry time has arrived."""

    def ack(self, record_id: str) -> None:
        """Mark a record as successfully delivered."""

    def nack(
        self,
        record_id: str,
        error: str,
        retry_delay: float = 10.0,
    ) -> None:
        """Mark delivery failed and schedule retry."""

    def dead(self, record_id: str, error: str) -> None:
        """Move a record to the dead-letter queue."""

    def count(self, state: RecordState | None = None) -> int:
        """Count records, optionally filtered by state."""

    def list_by_state(
        self,
        state: RecordState,
        limit: int = 100,
        offset: int = 0,
    ) -> list[StoredRecord]:
        """List records by state with pagination."""

    def iter_pending(self) -> Iterator[StoredRecord]:
        """Iterate over all pending records (for recovery)."""

    def delete_old(
        self,
        before: str,
        state: RecordState | None = None,
    ) -> int:
        """Delete records older than a timestamp. Returns count."""

    def cleanup(self) -> None:
        """Perform backend-specific maintenance."""
