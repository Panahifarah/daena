from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import lmdb

from daena.exceptions import BackendError
from daena.persistence.models import RecordState, StoredRecord

_REC_PREFIX = b"rec:"
_IDX_PENDING = b"idx:pending:"
_IDX_DELIVERED = b"idx:delivered:"
_IDX_FAILED = b"idx:failed:"
_IDX_DEAD = b"idx:dead:"
_IDX_RETRY = b"idx:retry:"

_PREFIX_MAP: dict[RecordState, bytes] = {
    RecordState.pending: _IDX_PENDING,
    RecordState.delivered: _IDX_DELIVERED,
    RecordState.failed: _IDX_FAILED,
    RecordState.dead: _IDX_DEAD,
}


class LMDBBackend:
    """LMDB-based persistence backend using key-prefix partitioning.

    Uses a single LMDB database with key prefixes to emulate named
    sub-databases.

    Key design:
      - rec:{record_id}          -> serialized record JSON
      - idx:pending:{ts}\x00{id}  -> "" (ordered FIFO queue)
      - idx:delivered:{ts}\x00{id} -> ""
      - idx:failed:{ts}\x00{id}   -> ""
      - idx:dead:{ts}\x00{id}     -> ""
      - idx:retry:{next}\x00{id}  -> ""
    """

    def __init__(
        self,
        path: str | Path = "/var/lib/daena/data",
        map_size: int = 104_857_600,
        max_databases: int = 16,
    ) -> None:
        self._path = Path(path)
        self._map_size = map_size
        self._max_databases = max_databases
        self._env: lmdb.Environment | None = None

    def _ensure_env(self) -> lmdb.Environment:
        if self._env is None:
            raise BackendError("Backend not opened")
        return self._env

    def open(self) -> None:
        self._path.mkdir(parents=True, exist_ok=True)
        self._env = lmdb.open(str(self._path), self._map_size, self._max_databases)

    def close(self) -> None:
        if self._env is not None:
            self._env.close()
            self._env = None

    def _rec_key(self, record_id: str) -> bytes:
        return _REC_PREFIX + record_id.encode()

    def _idx_key(self, prefix: bytes, record_id: str) -> bytes:
        ts = datetime.now(UTC).isoformat()
        return prefix + f"{ts}\x00{record_id}".encode()

    def _record_id_from_idx(self, key: bytes, prefix: bytes) -> str:
        suffix = key[len(prefix) :].decode()
        return suffix.split("\x00", 1)[1]

    def _read_record(self, txn: lmdb.Transaction, record_id: str) -> StoredRecord | None:
        raw = txn.get(self._rec_key(record_id))
        if raw is None:
            return None
        return StoredRecord.from_dict(json.loads(raw))

    def put(self, record: StoredRecord) -> None:
        env = self._ensure_env()
        rec_key = self._rec_key(record.record_id)
        value = json.dumps(record.to_dict()).encode()
        idx_key = self._idx_key(_IDX_PENDING, record.record_id)

        with env.begin(write=True) as txn:
            if txn.get(rec_key) is not None:
                return
            txn.put(rec_key, value)
            txn.put(idx_key, b"")

    def get(self, record_id: str) -> StoredRecord | None:
        env = self._ensure_env()
        key = self._rec_key(record_id)
        with env.begin() as txn:
            value = txn.get(key)
        if value is None:
            return None
        return StoredRecord.from_dict(json.loads(value))

    def update_state(
        self,
        record_id: str,
        state: RecordState,
        last_error: str | None = None,
        next_retry_at: str | None = None,
    ) -> None:
        env = self._ensure_env()
        rec_key = self._rec_key(record_id)
        now = datetime.now(UTC).isoformat()

        with env.begin(write=True) as txn:
            raw = txn.get(rec_key)
            if raw is None:
                return
            record_dict: dict[str, Any] = json.loads(raw)
            record_dict["state"] = state.value
            record_dict["updated_at"] = now
            if last_error is not None:
                record_dict["last_error"] = last_error
            if next_retry_at is not None:
                record_dict["next_retry_at"] = next_retry_at
            txn.put(rec_key, json.dumps(record_dict).encode())

            target_prefix = _PREFIX_MAP.get(state)
            if target_prefix and state != RecordState.pending:
                new_idx = self._idx_key(target_prefix, record_id)
                txn.put(new_idx, b"")

            if state == RecordState.failed and next_retry_at:
                retry_key = _IDX_RETRY + f"{next_retry_at}\x00{record_id}".encode()
                txn.put(retry_key, b"")

    def pending(self, limit: int = 100, older_than: str | None = None) -> list[StoredRecord]:
        _ = older_than
        return self._list_by_state_prefix(_IDX_PENDING, RecordState.pending, limit)

    def ready_for_retry(self, limit: int = 100, now: str | None = None) -> list[StoredRecord]:
        env = self._ensure_env()
        now_str = now or datetime.now(UTC).isoformat()
        results: list[StoredRecord] = []
        seen: set[str] = set()
        with env.begin() as txn:
            cursor = txn.cursor()
            if not cursor.set_range(_IDX_RETRY):
                return results
            for key, _ in cursor:
                if not key.startswith(_IDX_RETRY):
                    break
                record_id = self._record_id_from_idx(key, _IDX_RETRY)
                retry_ts = key[len(_IDX_RETRY) :].decode().split("\x00", 1)[0]
                if retry_ts > now_str:
                    break
                if record_id in seen:
                    continue
                seen.add(record_id)
                record = self._read_record(txn, record_id)
                if record and record.state == RecordState.failed:
                    results.append(record)
                    if len(results) >= limit:
                        break
        return results

    def ack(self, record_id: str) -> None:
        self.update_state(record_id, RecordState.delivered)

    def nack(self, record_id: str, error: str, retry_delay: float = 10.0) -> None:
        from datetime import timedelta

        next_retry = (datetime.now(UTC) + timedelta(seconds=retry_delay)).isoformat()
        self.update_state(
            record_id,
            RecordState.failed,
            last_error=error,
            next_retry_at=next_retry,
        )

    def dead(self, record_id: str, error: str) -> None:
        self.update_state(record_id, RecordState.dead, last_error=error)

    def count(self, state: RecordState | None = None) -> int:
        env = self._ensure_env()
        with env.begin() as txn:
            if state is None:
                cursor = txn.cursor()
                count = 0
                if cursor.set_range(_REC_PREFIX):
                    for key, _ in cursor:
                        if not key.startswith(_REC_PREFIX):
                            break
                        count += 1
                return count
            prefix = _PREFIX_MAP.get(state)
            if prefix is None:
                return 0
            cursor = txn.cursor()
            count = 0
            if cursor.set_range(prefix):
                for key, _ in cursor:
                    if not key.startswith(prefix):
                        break
                    record_id = self._record_id_from_idx(key, prefix)
                    record = self._read_record(txn, record_id)
                    if record and record.state == state:
                        count += 1
            return count

    def list_by_state(
        self, state: RecordState, limit: int = 100, offset: int = 0
    ) -> list[StoredRecord]:
        prefix = _PREFIX_MAP.get(state)
        if prefix is None:
            return []
        return self._list_by_state_prefix(prefix, state, limit, offset)

    def iter_pending(self) -> Iterator[StoredRecord]:
        seen: set[str] = set()
        env = self._ensure_env()
        with env.begin() as txn:
            cursor = txn.cursor()
            if cursor.set_range(_IDX_PENDING):
                for key, _ in cursor:
                    if not key.startswith(_IDX_PENDING):
                        break
                    record_id = self._record_id_from_idx(key, _IDX_PENDING)
                    if record_id in seen:
                        continue
                    seen.add(record_id)
                    record = self._read_record(txn, record_id)
                    if record and record.state == RecordState.pending:
                        yield record

    def delete_old(self, before: str, state: RecordState | None = None) -> int:
        env = self._ensure_env()
        removed = 0

        prefixes = [_IDX_DELIVERED, _IDX_DEAD]
        if state:
            p = _PREFIX_MAP.get(state)
            prefixes = [p] if p else []

        with env.begin(write=True) as txn:
            for prefix in prefixes:
                cursor = txn.cursor()
                if not cursor.set_range(prefix):
                    continue
                seen_del: set[str] = set()
                for key, _ in cursor:
                    if not key.startswith(prefix):
                        break
                    suffix = key[len(prefix) :].decode()
                    ts_part = suffix.split("\x00", 1)[0]
                    if ts_part > before:
                        break
                    record_id = suffix.split("\x00", 1)[1]
                    if record_id in seen_del:
                        continue
                    seen_del.add(record_id)
                    txn.delete(self._rec_key(record_id))
                    txn.delete(key)
                    removed += 1
        return removed

    def cleanup(self) -> None:
        pass

    def _list_by_state_prefix(
        self,
        prefix: bytes,
        state: RecordState,
        limit: int = 100,
        offset: int = 0,
    ) -> list[StoredRecord]:
        seen: set[str] = set()
        env = self._ensure_env()
        results: list[StoredRecord] = []
        with env.begin() as txn:
            cursor = txn.cursor()
            if not cursor.set_range(prefix):
                return results
            skipped = 0
            for key, _ in cursor:
                if not key.startswith(prefix):
                    break
                record_id = self._record_id_from_idx(key, prefix)
                if record_id in seen:
                    continue
                seen.add(record_id)
                record = self._read_record(txn, record_id)
                if record is None or record.state != state:
                    continue
                if skipped < offset:
                    skipped += 1
                    continue
                results.append(record)
                if len(results) >= limit:
                    break
        return results
