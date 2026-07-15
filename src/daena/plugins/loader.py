from __future__ import annotations

from importlib.metadata import entry_points

from daena.exceptions import PluginError
from daena.plugins.registry import get_registry

SOURCE_EP = "daena.sources"
PROCESSOR_EP = "daena.processors"
SINK_EP = "daena.sinks"


def discover_plugins() -> None:
    """Discover plugins via package entry points and register them."""
    registry = get_registry()
    errors: list[str] = []

    for ep in entry_points(group=SOURCE_EP):
        try:
            cls = ep.load()
            registry.register_source(ep.name, cls)
        except Exception as exc:
            errors.append(f"source {ep.name}: {exc}")

    for ep in entry_points(group=PROCESSOR_EP):
        try:
            cls = ep.load()
            registry.register_processor(ep.name, cls)
        except Exception as exc:
            errors.append(f"processor {ep.name}: {exc}")

    for ep in entry_points(group=SINK_EP):
        try:
            cls = ep.load()
            registry.register_sink(ep.name, cls)
        except Exception as exc:
            errors.append(f"sink {ep.name}: {exc}")

    if errors:
        raise PluginError("Plugin loading encountered errors:\n  " + "\n  ".join(errors))
