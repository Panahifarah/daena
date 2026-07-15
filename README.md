# daena

Collect, buffer, and forward logs and events from Linux to central observability backends.

## Overview

Daena is a modular, extensible Linux service that:

- Collects logs, events, and telemetry from pluggable sources
- Normalizes and processes records through a configurable pipeline
- Persists data locally in LMDB for durability, replay, and buffering
- Forwards records reliably to one or more remote sinks
- Exposes a gRPC API for management and inspection
- Provides a CLI for operational tasks
- Degrades gracefully under failures with retry, backoff, and dead-letter queues

## Architecture

```
Sources → [Processors] → Pipeline → Persistence (LMDB) → Sink Dispatcher → Remote
                                                              ↻ retry queue
```

Key design decisions:

- **Plugin architecture**: Sources, processors, and sinks are loaded via
  Python entry points. Add new ones by installing a package or registering
  in `pyproject.toml`.
- **Pluggable persistence**: The `Backend` protocol abstracts storage.
  MVP uses LMDB. Future: NATS JetStream.
- **Reliability-first**: Records survive restarts, sink failures trigger
  exponential backoff, and permanently failed records land in a dead-letter
  queue.

## Quick start

```bash
# Prerequisites: pyenv with Python 3.13, uv installed

# Clone and set up
git clone <repo> && cd daena
pyenv local 3.13.5
uv sync --extra dev

# Run with dummy source/sink (no external dependencies)
uv run python -c "
import asyncio
from daena.config import DaenaConfig, SourceConfig, SinkConfig
from daena.core.runtime import DaenaRuntime

async def main():
    config = DaenaConfig()
    config.sources = [SourceConfig(name='test', type='dummy',
        options={'interval': 1.0, 'message': 'hello'})]
    config.sinks = [SinkConfig(name='log', type='dummy')]
    config.persistence.lmdb.path = '/tmp/daena_data'

    runtime = DaenaRuntime(config)
    await runtime.start()
    await asyncio.sleep(5)
    print(f'Records: {runtime.backend.count()}')
    await runtime.stop()

asyncio.run(main())
"

# Run tests
uv run pytest tests/ -v

# Start gRPC server
uv run daena-serve

# Use the CLI (point at a running daena gRPC API)
uv run daena status
uv run daena health
uv run daena queue
```

## Project structure

```
daena/
├── pyproject.toml              # Project metadata, dependencies, entry points
├── Dockerfile                  # Container image
├── proto/daena/v1/daena.proto  # gRPC service definition
├── config/daena.yaml           # Example configuration
├── deploy/daena.service        # systemd unit file
├── .github/workflows/ci.yml    # CI pipeline
├── src/daena/
│   ├── app.py                  # `daena-serve` entry point (async gRPC)
│   ├── config.py               # YAML → pydantic config
│   ├── logutil.py              # structlog setup
│   ├── exceptions.py           # Domain exceptions
│   ├── api/
│   │   ├── grpc_server.py      # DaenaServicer + DaenaGRPCServer
│   │   └── pb2/                # Generated gRPC stubs
│   ├── cli/                    # Typer CLI (gRPC client)
│   ├── core/
│   │   ├── runtime.py          # Service lifecycle
│   │   └── pipeline.py         # Collection → persist → dispatch
│   ├── persistence/
│   │   ├── backend.py          # Abstract Backend protocol
│   │   ├── models.py           # RecordState, StoredRecord
│   │   └── lmdb.py             # LMDB implementation
│   ├── pipeline/
│   │   ├── base.py             # Source/Processor/Sink ABCs
│   │   ├── record.py           # In-memory Record dataclass
│   │   ├── sources/            # Built-in sources (dummy)
│   │   ├── sinks/              # Built-in sinks (dummy, http)
│   │   └── processors/         # Built-in processors (passthrough)
│   └── plugins/
│       ├── loader.py           # Entry-point discovery
│       └── registry.py         # Plugin registry
└── tests/
```

## Configuration

Daena loads configuration from `/etc/daena/daena.yaml`, `./daena.yaml`, or
`./config/daena.yaml`. See `config/daena.yaml` for a full example.

```yaml
logging:
  level: info
  format: json

api:
  grpc:
    host: 127.0.0.1
    port: 8642
    max_workers: 10

persistence:
  backend: lmdb
  lmdb:
    path: /var/lib/daena/data
    map_size: 104857600

sources:
  - name: system_logs
    type: journald       # future
    options: {}

processors:
  - name: add_hostname
    type: enricher       # future
    options: {}

sinks:
  - name: central
    type: http
    options:
      url: https://logs.example.com/ingest
```

## gRPC API

The gRPC API runs on `127.0.0.1:8642` with the following RPCs:

| RPC | Description |
|-----|-------------|
| `GetStatus` | Service status and version |
| `GetHealth` | Health check (backend, plugins, runtime) |
| `GetConfig` | Loaded configuration as JSON |
| `ListPlugins` | Registered sources, processors, and sinks |
| `GetQueueState` | Queue state counts (pending, delivered, failed, dead) |
| `ListPendingRecords` | Pending records with pagination |
| `ListDeadRecords` | Dead-letter records with pagination |
| `ListSinks` | Configured sinks |
| `ReloadConfig` | Reload service configuration at runtime |

### Reflect the gRPC service

```bash
# Install grpcurl to inspect the service
grpcurl -plaintext 127.0.0.1:8642 list
grpcurl -plaintext 127.0.0.1:8642 describe daena.v1.Daena
```

## CLI

Daena provides a CLI that connects to the gRPC server:

```bash
daena status       # Show service status
daena health       # Check health
daena queue        # Inspect queue state
daena sinks        # List configured sinks
daena plugins      # List registered plugins
daena config       # Show loaded configuration
daena version      # Show version
```

## Deployment

### systemd

```bash
# Create daena user
sudo useradd -r -s /sbin/nologin -d /var/lib/daena daena

# Install package
uv pip install .

# Set up directories
sudo mkdir -p /etc/daena /var/lib/daena /var/log/daena /run/daena
sudo cp config/daena.yaml /etc/daena/
sudo cp deploy/daena.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now daena
```

### Docker

```bash
# Build image
docker build -t daena:latest .

# Run with config
docker run -d \
  --name daena \
  -v /path/to/daena.yaml:/etc/daena/daena.yaml:ro \
  -v daena-data:/var/lib/daena \
  -p 8642:8642 \
  daena:latest
```

## Extending

Add a new source by creating a class that inherits `daena.pipeline.base.Source`
and registering it as an entry point:

```python
# my_sources.py
from daena.pipeline.base import Source
from daena.pipeline.record import Record

class MySource(Source):
    async def start(self):
        pass
    async def stop(self):
        pass
```

```toml
# pyproject.toml
[project.entry-points."daena.sources"]
my_source = "my_sources:MySource"
```

Same pattern applies for `Processor` and `Sink` base classes.

## Branch workflow

- `main` — stable integration branch
- `dev` — active development branch

Feature work happens on `dev` or topic branches. Merges to `main` represent
stable release checkpoints.
