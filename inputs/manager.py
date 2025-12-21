"""Input handler lifecycle manager."""

import asyncio
from typing import Any

from events import EventBus, EventType
from .base import InputHandler
from .registry import list_handlers


class InputManager:
    """Manages lifecycle of all input handlers.

    Handles:
    - Loading enabled handlers based on config
    - Starting all handlers as async tasks
    - Stopping all handlers on shutdown
    - Providing metadata about loaded handlers
    """

    def __init__(self, event_bus: EventBus, inputs_config: dict[str, Any] | None = None) -> None:
        """Initialize the manager.

        Args:
            event_bus: EventBus instance to pass to handlers
            inputs_config: Dict of handler configs keyed by handler name
                          e.g. {"osc": {"port": 8000}, "idle": {"timeout": 300}}
        """
        self.event_bus = event_bus
        self._inputs_config = inputs_config or {}
        self._handlers: dict[str, InputHandler] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}

    def load_enabled_handlers(self) -> list[str]:
        """Instantiate all enabled handlers.

        A handler is enabled if:
        - It's not in config (uses defaults, enabled=True)
        - It's in config without "enabled" key (enabled=True)
        - It's in config with "enabled": true

        Returns:
            List of handler names that were loaded
        """
        loaded = []

        for name, handler_cls in list_handlers().items():
            # Get config for this handler (empty dict if not specified)
            handler_config = self._inputs_config.get(name, {})

            # Check if enabled (default True)
            if not handler_config.get("enabled", True):
                print(f"Input handler '{name}' disabled in config")
                continue

            try:
                # Create config object from dict
                config_obj = handler_cls.config_class(**handler_config)

                # Instantiate handler
                handler = handler_cls(self.event_bus, config_obj)
                self._handlers[name] = handler
                loaded.append(name)

            except Exception as e:
                print(f"Failed to load handler '{name}': {e}")

        return loaded

    async def start_all(self) -> list[asyncio.Task[None]]:
        """Start all loaded handlers as async tasks.

        Returns:
            List of created tasks
        """
        for name, handler in self._handlers.items():
            task = asyncio.create_task(handler.run(), name=f"input_{name}")
            self._tasks[name] = task

        return list(self._tasks.values())

    def stop_all(self) -> None:
        """Stop all handlers."""
        for handler in self._handlers.values():
            try:
                handler.stop()
            except Exception as e:
                print(f"Error stopping handler '{handler.name}': {e}")

    def get_handler(self, name: str) -> InputHandler | None:
        """Get a loaded handler instance by name.

        Args:
            name: Handler name (case-insensitive)

        Returns:
            Handler instance or None if not loaded
        """
        return self._handlers.get(name.lower())

    def get_idle_event_types(self) -> list[EventType]:
        """Get all event types that should reset the idle timer.

        Collects `produces_events` from handlers where `resets_idle` is True.

        Returns:
            List of EventType values
        """
        types: list[EventType] = []
        for handler in self._handlers.values():
            if handler.resets_idle:
                types.extend(handler.produces_events)
        return types

    def get_status(self) -> dict[str, dict[str, Any]]:
        """Get status of all loaded handlers.

        Returns:
            Dict mapping handler names to status info
        """
        return {
            name: {
                "name": handler.name,
                "description": handler.description,
                "running": handler._running,
                "connected": handler.connected,
                "produces_events": [e.name for e in handler.produces_events],
                "resets_idle": handler.resets_idle,
            }
            for name, handler in self._handlers.items()
        }

    @property
    def handlers(self) -> dict[str, InputHandler]:
        """Get all loaded handler instances."""
        return self._handlers.copy()
