"""Idle timeout handler."""

import asyncio
import time

from events import EventBus, Event, EventType


class IdleHandler:
    """Handles idle timeout and triggers idle mode."""

    def __init__(self, event_bus: EventBus, timeout: float = 30.0) -> None:
        self.event_bus = event_bus
        self.timeout = timeout
        self._last_activity = time.time()
        self._is_idle = False
        self._running = False

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
        self._running = False
