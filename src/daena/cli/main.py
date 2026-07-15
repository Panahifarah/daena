from __future__ import annotations

import httpx
import typer
from rich.console import Console
from rich.table import Table

from daena._version import __version__

app = typer.Typer(
    name="daena",
    help="Daena: collect, buffer, and forward logs and events.",
)
console = Console()

DEFAULT_API_URL = "http://127.0.0.1:8642/api/v1"


def _client(timeout: float = 10.0) -> httpx.Client:
    return httpx.Client(timeout=httpx.Timeout(timeout))


def _api_url() -> str:
    return DEFAULT_API_URL  # TODO: make configurable via env/flag


@app.command()
def status() -> None:
    """Show daemon status."""
    try:
        with _client(5.0) as c:
            resp = c.get(f"{_api_url()}/system/status")
            resp.raise_for_status()
            data = resp.json()
            console.print(f"[bold]Daena[/bold] v{data.get('version', '?')}")
            console.print(f"Running: {data.get('running', '?')}")
    except httpx.ConnectError:
        console.print("[red]Cannot connect to daena service[/red]")
        raise typer.Exit(1) from None


@app.command()
def health() -> None:
    """Check service health."""
    try:
        with _client(5.0) as c:
            resp = c.get(f"{_api_url()}/system/health")
            resp.raise_for_status()
            data = resp.json()
            if data.get("healthy"):
                console.print("[green]Healthy[/green]")
            else:
                console.print("[red]Unhealthy[/red]")
                raise typer.Exit(1)
    except httpx.ConnectError:
        console.print("[red]Cannot connect to daena service[/red]")
        raise typer.Exit(1) from None


@app.command()
def queue() -> None:
    """Inspect queue state."""
    try:
        with _client() as c:
            resp = c.get(f"{_api_url()}/queue")
            resp.raise_for_status()
            data = resp.json()
            table = Table("State", "Count")
            for key in ("pending", "delivered", "failed", "dead", "total"):
                table.add_row(key, str(data.get(key, 0)))
            console.print(table)
    except httpx.ConnectError:
        console.print("[red]Cannot connect to daena service[/red]")
        raise typer.Exit(1) from None


@app.command()
def sinks() -> None:
    """List configured sinks."""
    try:
        with _client() as c:
            resp = c.get(f"{_api_url()}/sinks")
            resp.raise_for_status()
            data = resp.json()
            sinks_list = data.get("sinks", [])
            if not sinks_list:
                console.print("No sinks configured")
                return
            table = Table("Name", "Type")
            for s in sinks_list:
                table.add_row(s["name"], s["type"])
            console.print(table)
    except httpx.ConnectError:
        console.print("[red]Cannot connect to daena service[/red]")
        raise typer.Exit(1) from None


@app.command()
def plugins() -> None:
    """List loaded plugins."""
    try:
        with _client() as c:
            resp = c.get(f"{_api_url()}/plugins")
            resp.raise_for_status()
            data = resp.json()
            plugins_data = data.get("plugins", {})
            for category, items in plugins_data.items():
                if items:
                    table = Table(f"{category.title()}")
                    for item in items:
                        table.add_row(f"{item['name']} ({item['class']})")
                    console.print(table)
                    console.print()
    except httpx.ConnectError:
        console.print("[red]Cannot connect to daena service[/red]")
        raise typer.Exit(1) from None


@app.command()
def config() -> None:
    """Show loaded service configuration."""
    try:
        with _client() as c:
            resp = c.get(f"{_api_url()}/system/config")
            resp.raise_for_status()
            data = resp.json()
            console.print(data)
    except httpx.ConnectError:
        console.print("[red]Cannot connect to daena service[/red]")
        raise typer.Exit(1) from None


@app.command()
def version() -> None:
    """Show version."""
    console.print(f"daena v{__version__}")


if __name__ == "__main__":
    app()
