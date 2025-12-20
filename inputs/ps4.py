"""PS4 controller input handler."""

import asyncio
from enum import IntEnum
from typing import Any

from events import EventBus, Event, EventType


class PS4Button(IntEnum):
    """PS4 controller button mappings (may vary by platform)."""
    CROSS = 0      # X
    CIRCLE = 1     # O
    SQUARE = 2     # Square
    TRIANGLE = 3   # Triangle
    L1 = 4
    R1 = 5
    L2 = 6
    R2 = 7
    SHARE = 8
    OPTIONS = 9
    L3 = 10        # Left stick click
    R3 = 11        # Right stick click
    PS = 12
    TOUCHPAD = 13


class PS4Axis(IntEnum):
    """PS4 controller axis mappings."""
    LEFT_X = 0
    LEFT_Y = 1
    RIGHT_X = 2
    RIGHT_Y = 3
    L2 = 4
    R2 = 5


class PS4Controller:
    """PS4 controller input handler using pygame."""

    def __init__(self, event_bus: EventBus) -> None:
        self.event_bus = event_bus
        self._joystick: Any = None
        self._running = False
        self._pygame_initialized = False

        # State tracking
        self._button_state: dict[int, bool] = {}
        self._axis_state: dict[int, float] = {}

        # Deadzone for analog sticks
        self.deadzone = 0.15

    def _init_pygame(self) -> bool:
        """Initialize pygame and find controller."""
        try:
            import pygame
            pygame.init()
            pygame.joystick.init()

            if pygame.joystick.get_count() == 0:
                print("No controller found. Controller input disabled.")
                return False

            self._joystick = pygame.joystick.Joystick(0)
            self._joystick.init()
            print(f"Controller connected: {self._joystick.get_name()}")
            self._pygame_initialized = True
            return True
        except ImportError:
            print("Warning: pygame not installed. Controller input disabled.")
            return False

    def _apply_deadzone(self, value: float) -> float:
        """Apply deadzone to axis value."""
        if abs(value) < self.deadzone:
            return 0.0
        # Scale the remaining range to 0-1
        sign = 1 if value > 0 else -1
        return sign * (abs(value) - self.deadzone) / (1 - self.deadzone)

    async def run(self) -> None:
        """Run the controller input loop."""
        if not self._init_pygame():
            return

        import pygame

        self._running = True
        while self._running:
            # Process pygame events
            for event in pygame.event.get():
                if event.type == pygame.JOYBUTTONDOWN:
                    self._button_state[event.button] = True
                    await self.event_bus.publish(
                        Event(
                            type=EventType.CONTROLLER_BUTTON,
                            data={
                                "button": event.button,
                                "pressed": True,
                            }
                        )
                    )
                elif event.type == pygame.JOYBUTTONUP:
                    self._button_state[event.button] = False
                    await self.event_bus.publish(
                        Event(
                            type=EventType.CONTROLLER_BUTTON,
                            data={
                                "button": event.button,
                                "pressed": False,
                            }
                        )
                    )
                elif event.type == pygame.JOYAXISMOTION:
                    value = self._apply_deadzone(event.value)
                    if self._axis_state.get(event.axis) != value:
                        self._axis_state[event.axis] = value
                        await self.event_bus.publish(
                            Event(
                                type=EventType.CONTROLLER_AXIS,
                                data={
                                    "axis": event.axis,
                                    "value": value,
                                }
                            )
                        )
                elif event.type == pygame.JOYHATMOTION:
                    # D-pad as hat
                    await self.event_bus.publish(
                        Event(
                            type=EventType.CONTROLLER_BUTTON,
                            data={
                                "dpad": event.value,  # (x, y) tuple
                            }
                        )
                    )

            # Small delay to prevent busy-waiting
            await asyncio.sleep(0.016)  # ~60 Hz

    def stop(self) -> None:
        """Stop the controller handler."""
        self._running = False
        if self._pygame_initialized:
            import pygame
            pygame.quit()

    def get_axis(self, axis: int) -> float:
        """Get current axis value."""
        return self._axis_state.get(axis, 0.0)

    def is_pressed(self, button: int) -> bool:
        """Check if button is currently pressed."""
        return self._button_state.get(button, False)
