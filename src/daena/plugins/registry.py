from __future__ import annotations


class PluginRegistry:
    """Registry for plugin factories.

    Maintains separate maps for sources, processors, and sinks.
    Each entry maps plugin type name → factory callable.
    """

    def __init__(self) -> None:
        self._sources: dict[str, type] = {}
        self._processors: dict[str, type] = {}
        self._sinks: dict[str, type] = {}

    def register_source(self, name: str, cls: type) -> None:
        self._sources[name] = cls

    def register_processor(self, name: str, cls: type) -> None:
        self._processors[name] = cls

    def register_sink(self, name: str, cls: type) -> None:
        self._sinks[name] = cls

    def get_source(self, name: str) -> type | None:
        return self._sources.get(name)

    def get_processor(self, name: str) -> type | None:
        return self._processors.get(name)

    def get_sink(self, name: str) -> type | None:
        return self._sinks.get(name)

    def list_sources(self) -> dict[str, type]:
        return dict(self._sources)

    def list_processors(self) -> dict[str, type]:
        return dict(self._processors)

    def list_sinks(self) -> dict[str, type]:
        return dict(self._sinks)

    def all_plugins(self) -> dict[str, dict[str, type]]:
        return {
            "sources": self.list_sources(),
            "processors": self.list_processors(),
            "sinks": self.list_sinks(),
        }


_registry = PluginRegistry()


def get_registry() -> PluginRegistry:
    return _registry
