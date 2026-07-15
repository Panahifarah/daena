from __future__ import annotations

from pathlib import Path

from daena.config import DaenaConfig, load_config


def test_minimal_config_has_defaults() -> None:
    config = DaenaConfig()
    assert config.data_dir == "/var/lib/daena"
    assert config.logging.level == "info"
    assert config.api.http.port == 8642
    assert config.pipeline.batch_size == 100


def test_load_config_from_file(config_file: Path) -> None:
    config = load_config(str(config_file))
    assert config.data_dir == "/tmp/daena_data"
    assert config.logging.level == "debug"
    assert len(config.sources) == 1
    assert config.sources[0].name == "test"
    assert config.sources[0].type == "dummy"


def test_load_config_nonexistent_file() -> None:
    try:
        load_config("/nonexistent/daena.yaml")
        raise AssertionError("Expected FileNotFoundError")  # noqa: B011
    except FileNotFoundError:
        pass


def test_config_can_set_persistence_backend() -> None:
    config = DaenaConfig()
    assert config.persistence.backend == "lmdb"
    assert config.persistence.lmdb.map_size == 104_857_600


def test_config_source_options(minimal_config: DaenaConfig) -> None:
    cfg = minimal_config
    assert cfg.sources == []
    assert cfg.processors == []
    assert cfg.sinks == []
