from __future__ import annotations

import json

import grpc
import typer
from rich.console import Console
from rich.table import Table

from daena._version import __version__
from daena.api.pb2 import daena_pb2 as pb2
from daena.api.pb2 import daena_pb2_grpc as pb2_grpc

app = typer.Typer(
    name="daena",
    help="Daena: collect, buffer, and forward logs and events.",
)
console = Console()

DEFAULT_TARGET = "127.0.0.1:8642"


def _stub(target: str | None = None) -> pb2_grpc.DaenaStub:
    tgt = target or DEFAULT_TARGET
    channel = grpc.insecure_channel(tgt)
    return pb2_grpc.DaenaStub(channel)


def _connect(target: str | None = None) -> pb2_grpc.DaenaStub:
    try:
        stub = _stub(target)
        stub.GetStatus(pb2.Empty(), timeout=3.0)
        return stub
    except grpc.RpcError:
        console.print("[red]Cannot connect to daena service[/red]")
        raise typer.Exit(1) from None
    except Exception:
        console.print("[red]Cannot connect to daena service[/red]")
        raise typer.Exit(1) from None


@app.command()
def status() -> None:
    """Show daemon status."""
    stub = _connect()
    resp = stub.GetStatus(pb2.Empty(), timeout=5.0)
    console.print(f"[bold]Daena[/bold] v{resp.version}")
    console.print(f"Running: {resp.running}")


@app.command()
def health() -> None:
    """Check service health."""
    stub = _connect()
    resp = stub.GetHealth(pb2.Empty(), timeout=5.0)
    if resp.healthy:
        console.print("[green]Healthy[/green]")
    else:
        console.print("[red]Unhealthy[/red]")
        raise typer.Exit(1)


@app.command()
def queue() -> None:
    """Inspect queue state."""
    stub = _connect()
    resp = stub.GetQueueState(pb2.Empty(), timeout=5.0)
    table = Table("State", "Count")
    for key in ("pending", "delivered", "failed", "dead", "total"):
        table.add_row(key, str(getattr(resp, key, 0)))
    console.print(table)


@app.command()
def sinks() -> None:
    """List configured sinks."""
    stub = _connect()
    resp = stub.ListSinks(pb2.Empty(), timeout=5.0)
    items = resp.sinks
    if not items:
        console.print("No sinks configured")
        return
    table = Table("Name", "Type")
    for s in items:
        table.add_row(s.name, s.type)
    console.print(table)


@app.command()
def plugins() -> None:
    """List loaded plugins."""
    stub = _connect()
    resp = stub.ListPlugins(pb2.Empty(), timeout=5.0)
    for label, cat in (
        ("Sources", resp.sources),
        ("Processors", resp.processors),
        ("Sinks", resp.sinks),
    ):
        if cat.items:
            table = Table(label)
            for item in cat.items:
                table.add_row(f"{item.name} ({item.class_name})")
            console.print(table)
            console.print()


@app.command()
def config() -> None:
    """Show loaded service configuration."""
    stub = _connect()
    resp = stub.GetConfig(pb2.Empty(), timeout=5.0)
    parsed = json.loads(resp.config_json)
    console.print(parsed)


@app.command()
def version() -> None:
    """Show version."""
    console.print(f"daena v{__version__}")


if __name__ == "__main__":
    app()
