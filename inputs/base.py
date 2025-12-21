"""Base class for input handlers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar

from events import EventBus, EventType


@dataclass
class InputConfig:
    """Base configuration for input handlers.

    Subclasses should extend this with handler-specific fields.
    All fields should have defaults so handlers work out of the box.
    """
    enabled: bool = True


class InputHandler(ABC):
    """Abstract base class for all input handlers.

    To create a new input handler:
    1. Extend this class
    2. Define class-level metadata (name, description, etc.)
    3. Create a config dataclass extending InputConfig
    4. Implement run() async method
    5. Optionally override stop() for cleanup
    6. Add @register decorator from registry.py

    Example:
        @dataclass
        class MyConfig(InputConfig):
            port: int = 8080

        @register
        class MyHandler(InputHandler):
            name = "my_handler"
            description = "Does something cool"
            config_class = MyConfig
            produces_events = [EventType.CONTROLLER_BUTTON]

            async def run(self) -> None:
                self._running = True
                while self._running:
                    # ... handle input
                    await asyncio.sleep(0.1)
    """

    # Class-level metadata - override in subclasses
    name: ClassVar[str] = "unknown"
    description: ClassVar[str] = ""
    config_class: ClassVar[type[InputConfig]] = InputConfig
    produces_events: ClassVar[list[EventType]] = []
    resets_idle: ClassVar[bool] = True  # Whether events from this handler reset idle timer

    def __init__(self, event_bus: EventBus, config: InputConfig | None = None) -> None:
        """Initialize the handler.

        Args:
            event_bus: EventBus instance for publishing events
            config: Handler-specific configuration (uses defaults if None)
        """
        self.event_bus = event_bus
        self.config = config or self.config_class()
        self._running = False

    @abstractmethod
    async def run(self) -> None:
        """Main async loop for the handler.

        Should set self._running = True at start and check it in the loop.
        Must be cancellable (handle asyncio.CancelledError gracefully).
        """
        pass

    def stop(self) -> None:
        """Stop the handler.

        Override this method for custom cleanup (closing connections, etc.).
        Always call super().stop() or set self._running = False.
        """
        self._running = False

    @property
    def connected(self) -> bool:
        """Whether the handler's device/service is currently connected.

        Override for hot-connect handlers (controllers, MIDI devices, etc.).
        Default returns True for handlers without connection state.
        """
        return True

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r} running={self._running}>"
