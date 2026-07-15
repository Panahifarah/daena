from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LoggingConfig(BaseSettings):
    level: str = "info"
    format: str = "json"
    file: str | None = None


class APIHTTPConfig(BaseSettings):
    host: str = "127.0.0.1"
    port: int = 8642
    workers: int = 1


class APIConfig(BaseSettings):
    http: APIHTTPConfig = APIHTTPConfig()


class SinkRetryConfig(BaseSettings):
    max_attempts: int = 5
    min_delay: float = 1.0
    max_delay: float = 120.0
    multiplier: float = 2.0


class SinkConfig(BaseSettings):
    name: str
    type: str
    enabled: bool = True
    retry: SinkRetryConfig = SinkRetryConfig()
    options: dict[str, Any] = Field(default_factory=dict)


class SourceConfig(BaseSettings):
    name: str
    type: str
    enabled: bool = True
    options: dict[str, Any] = Field(default_factory=dict)


class ProcessorConfig(BaseSettings):
    name: str
    type: str
    enabled: bool = True
    options: dict[str, Any] = Field(default_factory=dict)


class LMDBConfig(BaseSettings):
    path: str = "/var/lib/daena/data"
    map_size: int = 104_857_600
    max_databases: int = 16


class PersistenceConfig(BaseSettings):
    backend: str = "lmdb"
    lmdb: LMDBConfig = LMDBConfig()
    options: dict[str, Any] = Field(default_factory=dict)


class PipelineConfig(BaseSettings):
    batch_size: int = 100
    flush_interval: float = 5.0
    max_queue_size: int = 10_000


class DaenaConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DAENA_", extra="ignore")

    data_dir: str = "/var/lib/daena"
    log_dir: str = "/var/log/daena"
    pid_file: str = "/run/daena/daena.pid"

    logging: LoggingConfig = LoggingConfig()
    api: APIConfig = APIConfig()
    pipeline: PipelineConfig = PipelineConfig()
    persistence: PersistenceConfig = PersistenceConfig()

    sources: list[SourceConfig] = Field(default_factory=list)
    processors: list[ProcessorConfig] = Field(default_factory=list)
    sinks: list[SinkConfig] = Field(default_factory=list)

    @field_validator("data_dir", "log_dir", mode="before")
    @classmethod
    def ensure_trailing(cls, v: str) -> str:
        return v.rstrip("/")


def load_config(path: str | Path | None = None) -> DaenaConfig:
    config = DaenaConfig()
    if path:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Configuration file not found: {p}")
        with open(p) as f:
            raw: dict[str, Any] = yaml.safe_load(f) or {}
        merged = config.model_dump()
        merged.update(raw)
        config = DaenaConfig(**merged)
    return config
