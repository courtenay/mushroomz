"""Manual control scene - direct PS4 controller manipulation."""

import sys
import time
from typing import Any

from .base import Scene
from .state import is_manual_active, set_manual_active
from fixtures.mushroom import Mushroom
from fixtures.rgb_par import Color
from events import Event, EventType
from inputs.ps4 import PS4Axis

# Gyro sensitivity multipliers
GYRO_HUE_SENSITIVITY = 200.0  # degrees per second per unit gyro
GYRO_SAT_SENSITIVITY = 0.5    # saturation change per second per unit gyro


class ManualScene(Scene):
    """Direct controller manipulation of lighting."""

    name = "Manual"

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        super().__init__(params)
        self._hue = 0.0
        self._saturation = 1.0
        self._brightness = 0.8

        # Axis states
        self._left_x = 0.0
        self._left_y = 0.0
        self._right_x = 0.0
        self._right_y = 0.0

        # Gyro states
        self._gyro_x = 0.0  # Roll - mapped to hue
        self._gyro_y = 0.0  # Pitch - mapped to saturation
        self._gyro_z = 0.0  # Yaw

        # Display rate limiting
        self._last_display = 0.0

    def activate(self) -> None:
        super().activate()
        set_manual_active(True)

    def deactivate(self) -> None:
        super().deactivate()
        set_manual_active(False)
        # Clear the line when leaving manual mode
        sys.stdout.write("\r" + " " * 80 + "\r")
        sys.stdout.flush()

    def _update_display(self) -> None:
        """Update the terminal status line with stick position."""
        now = time.time()
        if now - self._last_display < 0.05:  # 20fps max
            return
        self._last_display = now

        # Create position indicators (-1 to 1 mapped to bar)
        bar_len = 9
        mid = bar_len // 2

        def stick_bar(val: float) -> str:
            pos = int((val + 1) / 2 * (bar_len - 1))
            bar = ["-"] * bar_len
            bar[mid] = "|"
            bar[pos] = "●"
            return "".join(bar)

        # Color codes
        reset = "\033[0m"
        green = "\033[32m"
        blue = "\033[34m"
        yellow = "\033[33m"

        status = (
            f"\r{green}🎮{reset} "
            f"LX[{stick_bar(self._left_x)}] "
            f"LY[{stick_bar(self._left_y)}] "
            f"{blue}RY[{stick_bar(self._right_y)}]{reset} "
            f"{yellow}H:{self._hue:3.0f}° S:{self._saturation:.0%} B:{self._brightness:.0%}{reset}"
            + " " * 20  # Padding to overwrite audio display
        )
        sys.stdout.write(status)
        sys.stdout.flush()

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

        # Gyro adds to hue and saturation control
        # Roll (X) rotates hue, Pitch (Y) adjusts saturation
        self._hue = (self._hue + self._gyro_z * dt * GYRO_HUE_SENSITIVITY) % 360
        sat_gyro = -self._gyro_x * dt * GYRO_SAT_SENSITIVITY
        self._saturation = max(0, min(1, self._saturation + sat_gyro))

        color = Color.from_hsv(self._hue, self._saturation, self._brightness)
        mushroom.set_target(color)
        mushroom.update(dt, smoothing=0.5)

        self._update_display()

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

        elif event.type == EventType.CONTROLLER_GYRO:
            self._gyro_x = event.data.get("x", 0.0)
            self._gyro_y = event.data.get("y", 0.0)
            self._gyro_z = event.data.get("z", 0.0)
