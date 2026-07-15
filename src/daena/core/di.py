from __future__ import annotations

from typing import Any


class Container:
    """Minimal dependency injection container.

    Provides singleton and factory resolution for service components.
    """

    def __init__(self) -> None:
        self._instances: dict[str, Any] = {}
        self._factories: dict[str, callable] = {}

    def register(self, key: str, instance: Any) -> None:
        self._instances[key] = instance

    def register_factory(self, key: str, factory: callable) -> None:
        self._factories[key] = factory

    def resolve(self, key: str) -> Any:
        if key in self._instances:
            return self._instances[key]
        if key in self._factories:
            instance = self._factories[key]()
            self._instances[key] = instance
            return instance
        raise KeyError(f"No component registered for: {key}")

    def has(self, key: str) -> bool:
        return key in self._instances or key in self._factories
