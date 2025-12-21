"""Idle timeout handler."""

import asyncio
import time
from dataclasses import dataclass

from events import EventBus, Event, EventType
from .base import InputHandler, InputConfig
from .registry import register


@dataclass
class IdleConfig(InputConfig):
    """Configuration for idle handler."""
    timeout: float = 30.0  # Seconds before idle mode triggers


@register
class IdleHandler(InputHandler):
    """Handles idle timeout and triggers idle mode.

    Publishes IDLE_TIMEOUT events when no activity is detected
    for the configured timeout period. Other handlers should call
    activity() to reset the timer.
    """

    name = "idle"
    description = "Idle timeout handler - triggers pastel fade after inactivity"
    config_class = IdleConfig
    produces_events = [EventType.IDLE_TIMEOUT]
    resets_idle = False  # This handler doesn't reset itself

    def __init__(self, event_bus: EventBus, config: IdleConfig | None = None) -> None:
        super().__init__(event_bus, config)
        self.timeout = self.config.timeout if isinstance(self.config, IdleConfig) else 30.0
        self._last_activity = time.time()
        self._is_idle = False

    def activity(self) -> None:
        """Record activity (resets idle timer)."""
        self._last_activity = time.time()
        self._is_idle = False

    async def run(self) -> None:
        """Run the idle check loop."""
        self._running = True
        while self._running:
            await asyncio.sleep(1.0)

            if not self._is_idle:
                elapsed = time.time() - self._last_activity
                if elapsed >= self.timeout:
                    self._is_idle = True
                    await self.event_bus.publish(
                        Event(
                            type=EventType.IDLE_TIMEOUT,
                            data={"elapsed": elapsed}
                        )
                    )

    def stop(self) -> None:
        """Stop the idle handler."""
        super().stop()
