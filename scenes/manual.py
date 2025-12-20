"""Manual control scene - direct PS4 controller manipulation."""

from .base import Scene
from fixtures.mushroom import Mushroom
from fixtures.rgb_par import Color
from events import Event, EventType
from inputs.ps4 import PS4Axis


class ManualScene(Scene):
    """Direct controller manipulation of lighting."""

    name = "Manual"

    def __init__(self) -> None:
        super().__init__()
        self._hue = 0.0
        self._saturation = 1.0
        self._brightness = 0.8

        # Axis states
        self._left_x = 0.0
        self._left_y = 0.0
        self._right_x = 0.0
        self._right_y = 0.0

    def activate(self) -> None:
        super().activate()
        # Keep current values on activation

    def update(self, mushroom: Mushroom, dt: float) -> None:
        # Left stick controls hue and saturation
        # X axis: hue rotation
        self._hue = (self._hue + self._left_x * dt * 360) % 360

        # Y axis: saturation (up = more saturated)
        sat_change = -self._left_y * dt * 1.5
        self._saturation = max(0, min(1, self._saturation + sat_change))

        # Right stick Y controls brightness
        bright_change = -self._right_y * dt * 1.5
        self._brightness = max(0.1, min(1, self._brightness + bright_change))

        color = Color.from_hsv(self._hue, self._saturation, self._brightness)
        mushroom.set_target(color)
        mushroom.update(dt, smoothing=0.5)

    def handle_event(self, event: Event, mushroom: Mushroom) -> None:
        if event.type == EventType.CONTROLLER_AXIS:
            axis = event.data.get("axis")
            value = event.data.get("value", 0.0)

            if axis == PS4Axis.LEFT_X:
                self._left_x = value
            elif axis == PS4Axis.LEFT_Y:
                self._left_y = value
            elif axis == PS4Axis.RIGHT_X:
                self._right_x = value
            elif axis == PS4Axis.RIGHT_Y:
                self._right_y = value
