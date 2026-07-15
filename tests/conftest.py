from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml

from daena.config import DaenaConfig
from daena.persistence.lmdb import LMDBBackend
from daena.persistence.models import StoredRecord


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> Path:
    return tmp_path / "lmdb"


@pytest.fixture
def lmdb_backend(tmp_db_path: Path) -> Iterator[LMDBBackend]:
    backend = LMDBBackend(
        path=str(tmp_db_path),
        map_size=10_485_760,
    )
    backend.open()
    yield backend
    backend.close()


@pytest.fixture
def sample_record() -> StoredRecord:
    return StoredRecord(
        source="test_source",
        record_type="test",
        body={"message": "hello"},
        metadata={"env": "test"},
    )


@pytest.fixture
def minimal_config() -> DaenaConfig:
    return DaenaConfig()


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    path = tmp_path / "daena.yaml"
    data = {
        "data_dir": "/tmp/daena_data",
        "logging": {"level": "debug", "format": "json"},
        "sources": [
            {
                "name": "test",
                "type": "dummy",
                "enabled": True,
                "options": {"interval": 1.0},
            }
        ],
        "sinks": [
            {
                "name": "output",
                "type": "dummy",
                "enabled": True,
                "options": {},
            }
        ],
    }
    with open(path, "w") as f:
        yaml.dump(data, f)
    return path
