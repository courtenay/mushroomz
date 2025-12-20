"""Event types and event bus for the lighting system."""

import asyncio
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any


class EventType(Enum):
    """Types of events in the system."""
    # Controller events
    CONTROLLER_BUTTON = auto()
    CONTROLLER_AXIS = auto()
    CONTROLLER_GYRO = auto()  # Gyroscope data (pitch, yaw, roll rates)
    CONTROLLER_ACCEL = auto()  # Accelerometer data (x, y, z)

    # OSC events
    OSC_AUDIO_BEAT = auto()
    OSC_AUDIO_LEVEL = auto()
    OSC_BIO = auto()

    # System events
    IDLE_TIMEOUT = auto()
    SCENE_CHANGE = auto()
    MUSHROOM_SELECT = auto()


@dataclass
class Event:
    """Base event class."""
    type: EventType
    data: dict[str, Any]
    mushroom_id: int | None = None  # None means all mushrooms


class EventBus:
    """Async event bus for decoupled communication."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._handlers: dict[EventType, list[Any]] = {}

    def subscribe(self, event_type: EventType, handler: Any) -> None:
        """Subscribe a handler to an event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: EventType, handler: Any) -> None:
        """Unsubscribe a handler from an event type."""
        if event_type in self._handlers:
            self._handlers[event_type].remove(handler)

    async def publish(self, event: Event) -> None:
        """Publish an event to the queue."""
        await self._queue.put(event)

    def publish_sync(self, event: Event) -> None:
        """Publish an event synchronously (for use in callbacks)."""
        self._queue.put_nowait(event)

    async def process(self) -> None:
        """Process events from the queue. Run this in the main loop."""
        while True:
            event = await self._queue.get()
            handlers = self._handlers.get(event.type, [])
            for handler in handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event)
                    else:
                        handler(event)
                except Exception as e:
                    print(f"Error in event handler: {e}")
            self._queue.task_done()
