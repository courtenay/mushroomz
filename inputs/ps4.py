"""PS4 controller input handler with Bluetooth hot-connect support."""

import asyncio
from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from events import EventBus, Event, EventType
from .base import InputHandler, InputConfig
from .registry import register


# Connection check interval when no controller connected
RECONNECT_POLL_INTERVAL = 2.0  # seconds


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
    # D-pad as buttons (macOS)
    DPAD_UP = 11
    DPAD_DOWN = 12
    DPAD_LEFT = 13
    DPAD_RIGHT = 14


class PS4Axis(IntEnum):
    """PS4 controller axis mappings."""
    LEFT_X = 0
    LEFT_Y = 1
    RIGHT_X = 2
    RIGHT_Y = 3
    L2 = 4
    R2 = 5


@dataclass
class PS4Config(InputConfig):
    """Configuration for PS4 controller."""
    deadzone: float = 0.15


@register
class PS4Controller(InputHandler):
    """PS4 controller input handler using pygame with Bluetooth hot-connect.

    Supports hot-connect/disconnect of controllers via Bluetooth or USB.
    Publishes button and axis events for scene control.
    """

    name = "ps4"
    description = "PS4 DualShock controller via pygame"
    config_class = PS4Config
    produces_events = [EventType.CONTROLLER_BUTTON, EventType.CONTROLLER_AXIS]

    def __init__(self, event_bus: EventBus, config: PS4Config | None = None) -> None:
        super().__init__(event_bus, config)
        self._joystick: Any = None
        self._pygame_available = False
        self._connected = False

        # State tracking
        self._button_state: dict[int, bool] = {}
        self._axis_state: dict[int, float] = {}

        # Deadzone for analog sticks
        self.deadzone = self.config.deadzone if isinstance(self.config, PS4Config) else 0.15

    def _init_pygame(self) -> bool:
        """Initialize pygame (once). Returns True if pygame is available."""
        if self._pygame_available:
            return True
        try:
            import pygame
            pygame.init()
            pygame.joystick.init()
            self._pygame_available = True
            print("Controller subsystem initialized. Waiting for controller...")
            return True
        except ImportError:
            print("Warning: pygame not installed. Controller input disabled.")
            return False

    def _try_connect(self) -> bool:
        """Attempt to connect to a controller. Returns True if connected."""
        if not self._pygame_available:
            return False

        import pygame

        # Re-scan for joysticks (pygame 2.x supports this without quit/init)
        try:
            count = pygame.joystick.get_count()
        except pygame.error:
            return False

        if count == 0:
            return False

        try:
            self._joystick = pygame.joystick.Joystick(0)
            self._joystick.init()
            self._connected = True
            print(f"Controller connected: {self._joystick.get_name()}")
            return True
        except pygame.error as e:
            print(f"Failed to initialize controller: {e}")
            return False

    def _handle_disconnect(self) -> None:
        """Handle controller disconnection."""
        if self._connected:
            print("Controller disconnected. Waiting for reconnection...")
            self._connected = False
            self._joystick = None
            self._button_state.clear()
            self._axis_state.clear()

    def _apply_deadzone(self, value: float) -> float:
        """Apply deadzone to axis value."""
        if abs(value) < self.deadzone:
            return 0.0
        # Scale the remaining range to 0-1
        sign = 1 if value > 0 else -1
        return sign * (abs(value) - self.deadzone) / (1 - self.deadzone)

    async def run(self) -> None:
        """Run the controller input loop with hot-connect support."""
        if not self._init_pygame():
            return

        import pygame

        self._running = True
        last_connect_check = 0.0

        while self._running:
            # If not connected, poll for new controller
            if not self._connected:
                import time
                now = time.monotonic()
                if now - last_connect_check >= RECONNECT_POLL_INTERVAL:
                    last_connect_check = now
                    if self._try_connect():
                        # Publish connection event
                        await self.event_bus.publish(
                            Event(
                                type=EventType.CONTROLLER_BUTTON,
                                data={"connected": True}
                            )
                        )
                await asyncio.sleep(0.1)  # Slower polling when disconnected
                continue

            # Process pygame events
            try:
                events = pygame.event.get()
            except (pygame.error, KeyError):
                # Controller disconnected during event fetch
                self._handle_disconnect()
                await self.event_bus.publish(
                    Event(
                        type=EventType.CONTROLLER_BUTTON,
                        data={"connected": False}
                    )
                )
                continue

            try:
                for event in events:
                    if event.type == pygame.JOYBUTTONDOWN:
                        self._button_state[event.button] = True
                        # Convert D-pad buttons to dpad events (macOS)
                        dpad_map = {
                            PS4Button.DPAD_UP: (0, 1),
                            PS4Button.DPAD_DOWN: (0, -1),
                            PS4Button.DPAD_LEFT: (-1, 0),
                            PS4Button.DPAD_RIGHT: (1, 0),
                        }
                        if event.button in dpad_map:
                            await self.event_bus.publish(
                                Event(
                                    type=EventType.CONTROLLER_BUTTON,
                                    data={"dpad": dpad_map[event.button]}
                                )
                            )
                        else:
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
                        # Skip D-pad buttons (handled separately)
                        if event.button not in (PS4Button.DPAD_UP, PS4Button.DPAD_DOWN,
                                                PS4Button.DPAD_LEFT, PS4Button.DPAD_RIGHT):
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
                    elif event.type == pygame.JOYDEVICEREMOVED:
                        # Handle explicit device removal event
                        self._handle_disconnect()
                        await self.event_bus.publish(
                            Event(
                                type=EventType.CONTROLLER_BUTTON,
                                data={"connected": False}
                            )
                        )
                    elif event.type == pygame.JOYDEVICEADDED:
                        # Handle explicit device add event (reconnection)
                        if not self._connected:
                            self._try_connect()
                            await self.event_bus.publish(
                                Event(
                                    type=EventType.CONTROLLER_BUTTON,
                                    data={"connected": True}
                                )
                            )
            except (pygame.error, KeyError, OSError):
                # Controller likely disconnected mid-read
                self._handle_disconnect()
                await self.event_bus.publish(
                    Event(
                        type=EventType.CONTROLLER_BUTTON,
                        data={"connected": False}
                    )
                )
                continue

            # Small delay to prevent busy-waiting
            await asyncio.sleep(0.008)  # ~120 Hz for responsive sticks

    def stop(self) -> None:
        """Stop the controller handler."""
        super().stop()
        if self._pygame_available:
            import pygame
            pygame.quit()

    @property
    def connected(self) -> bool:
        """Check if a controller is currently connected."""
        return self._connected

    def get_axis(self, axis: int) -> float:
        """Get current axis value."""
        return self._axis_state.get(axis, 0.0)

    def is_pressed(self, button: int) -> bool:
        """Check if button is currently pressed."""
        return self._button_state.get(button, False)
