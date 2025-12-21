"""Input handler registry for plugin discovery."""

from typing import Type

from .base import InputHandler


# Global registry of handler classes
_handlers: dict[str, Type[InputHandler]] = {}


def register(cls: Type[InputHandler]) -> Type[InputHandler]:
    """Decorator to register an input handler class.

    Usage:
        @register
        class MyHandler(InputHandler):
            name = "my_handler"
            ...

    The handler will be registered under its `name` class attribute (lowercase).
    """
    name = cls.name.lower()
    if name in _handlers:
        raise ValueError(f"Handler '{name}' is already registered")
    _handlers[name] = cls
    return cls


def get_handler(name: str) -> Type[InputHandler] | None:
    """Get a registered handler class by name.

    Args:
        name: Handler name (case-insensitive)

    Returns:
        Handler class or None if not found
    """
    return _handlers.get(name.lower())


def list_handlers() -> dict[str, Type[InputHandler]]:
    """Get all registered handlers.

    Returns:
        Dict mapping handler names to their classes
    """
    return _handlers.copy()


def unregister(name: str) -> bool:
    """Remove a handler from the registry.

    Primarily useful for testing.

    Args:
        name: Handler name to remove

    Returns:
        True if handler was removed, False if not found
    """
    name = name.lower()
    if name in _handlers:
        del _handlers[name]
        return True
    return False


def clear_registry() -> None:
    """Clear all registered handlers.

    Primarily useful for testing.
    """
    _handlers.clear()
