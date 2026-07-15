from __future__ import annotations

from daena.persistence.lmdb import LMDBBackend
from daena.persistence.models import RecordState, StoredRecord


def test_put_and_get(lmdb_backend: LMDBBackend, sample_record: StoredRecord) -> None:
    lmdb_backend.put(sample_record)
    retrieved = lmdb_backend.get(sample_record.record_id)
    assert retrieved is not None
    assert retrieved.record_id == sample_record.record_id
    assert retrieved.source == "test_source"
    assert retrieved.body == {"message": "hello"}


def test_pending_returns_new_records(
    lmdb_backend: LMDBBackend, sample_record: StoredRecord
) -> None:
    lmdb_backend.put(sample_record)
    pending = lmdb_backend.pending(limit=10)
    assert len(pending) == 1
    assert pending[0].record_id == sample_record.record_id


def test_ack(lmdb_backend: LMDBBackend, sample_record: StoredRecord) -> None:
    lmdb_backend.put(sample_record)
    lmdb_backend.ack(sample_record.record_id)
    retrieved = lmdb_backend.get(sample_record.record_id)
    assert retrieved is not None
    assert retrieved.state == RecordState.delivered
    pending = lmdb_backend.pending()
    assert all(r.record_id != sample_record.record_id for r in pending)


def test_nack(lmdb_backend: LMDBBackend, sample_record: StoredRecord) -> None:
    lmdb_backend.put(sample_record)
    lmdb_backend.nack(sample_record.record_id, error="test error", retry_delay=1.0)
    retrieved = lmdb_backend.get(sample_record.record_id)
    assert retrieved is not None
    assert retrieved.state == RecordState.failed
    assert retrieved.last_error == "test error"
    assert retrieved.next_retry_at is not None


def test_dead(lmdb_backend: LMDBBackend, sample_record: StoredRecord) -> None:
    lmdb_backend.put(sample_record)
    lmdb_backend.dead(sample_record.record_id, error="permanent failure")
    retrieved = lmdb_backend.get(sample_record.record_id)
    assert retrieved is not None
    assert retrieved.state == RecordState.dead


def test_count(lmdb_backend: LMDBBackend, sample_record: StoredRecord) -> None:
    assert lmdb_backend.count() == 0
    lmdb_backend.put(sample_record)
    assert lmdb_backend.count() == 1
    assert lmdb_backend.count(RecordState.pending) == 1


def test_list_by_state(lmdb_backend: LMDBBackend, sample_record: StoredRecord) -> None:
    lmdb_backend.put(sample_record)
    pending = lmdb_backend.list_by_state(RecordState.pending)
    assert len(pending) == 1
    lmdb_backend.ack(sample_record.record_id)
    delivered = lmdb_backend.list_by_state(RecordState.delivered)
    assert len(delivered) == 1


def test_delete_old(lmdb_backend: LMDBBackend, sample_record: StoredRecord) -> None:
    lmdb_backend.put(sample_record)
    lmdb_backend.ack(sample_record.record_id)
    before = "2100-01-01T00:00:00"
    removed = lmdb_backend.delete_old(before, state=RecordState.delivered)
    assert removed == 1
    assert lmdb_backend.get(sample_record.record_id) is None


def test_iter_pending(lmdb_backend: LMDBBackend, sample_record: StoredRecord) -> None:
    lmdb_backend.put(sample_record)
    records = list(lmdb_backend.iter_pending())
    assert len(records) == 1
    assert records[0].record_id == sample_record.record_id


def test_update_state(lmdb_backend: LMDBBackend, sample_record: StoredRecord) -> None:
    lmdb_backend.put(sample_record)
    lmdb_backend.update_state(sample_record.record_id, RecordState.failed, last_error="oops")
    retrieved = lmdb_backend.get(sample_record.record_id)
    assert retrieved is not None
    assert retrieved.state == RecordState.failed
    assert retrieved.last_error == "oops"


def test_stored_record_to_from_dict(sample_record: StoredRecord) -> None:
    d = sample_record.to_dict()
    restored = StoredRecord.from_dict(d)
    assert restored.record_id == sample_record.record_id
    assert restored.source == sample_record.source
    assert restored.body == sample_record.body
    assert restored.state == sample_record.state


def test_ready_for_retry(lmdb_backend: LMDBBackend, sample_record: StoredRecord) -> None:
    lmdb_backend.put(sample_record)
    lmdb_backend.nack(sample_record.record_id, "retry later", retry_delay=0)
    ready = lmdb_backend.ready_for_retry(limit=10)
    assert len(ready) == 1
