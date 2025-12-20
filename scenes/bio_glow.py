"""Bio glow scene - reactive to plant resistance sensors."""

import math
from typing import Any

from .base import Scene
from fixtures.mushroom import Mushroom
from fixtures.rgb_par import Color
from events import Event, EventType


class BioGlowScene(Scene):
    """Plant bio-resistance reactive lighting."""

    name = "Bio Glow"

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        super().__init__(params)
        self._resistance: dict[int, float] = {}  # Per-mushroom resistance values
        self._smoothed: dict[int, float] = {}    # Smoothed values
        self._time = 0.0

    @property
    def low_color(self) -> tuple[float, float, float]:
        """HSV color for low resistance (default: deep green)."""
        color = self._params.get("low_color", [120, 0.6, 0.4])
        return (color[0], color[1], color[2])

    @property
    def high_color(self) -> tuple[float, float, float]:
        """HSV color for high resistance (default: bright yellow)."""
        color = self._params.get("high_color", [60, 0.8, 0.9])
        return (color[0], color[1], color[2])

    def activate(self) -> None:
        super().activate()
        self._time = 0.0

    def update(self, mushroom: Mushroom, dt: float) -> None:
        self._time += dt

        # Get resistance value for this mushroom (default to gentle pulse)
        raw = self._resistance.get(mushroom.id, 0.5)

        # Smooth the value
        if mushroom.id not in self._smoothed:
            self._smoothed[mushroom.id] = raw
        else:
            self._smoothed[mushroom.id] += (raw - self._smoothed[mushroom.id]) * dt * 2

        resistance = self._smoothed[mushroom.id]

        # Add gentle organic movement
        organic_pulse = math.sin(self._time * 0.5 + mushroom.id) * 0.1
        resistance = max(0, min(1, resistance + organic_pulse))

        # Interpolate between low and high colors
        h1, s1, v1 = self.low_color
        h2, s2, v2 = self.high_color

        h = h1 + (h2 - h1) * resistance
        s = s1 + (s2 - s1) * resistance
        v = v1 + (v2 - v1) * resistance

        color = Color.from_hsv(h, s, v)
        mushroom.set_target(color)
        mushroom.update(dt, smoothing=0.08)

    def handle_event(self, event: Event, mushroom: Mushroom) -> None:
        if event.type == EventType.OSC_BIO:
            # Update resistance for the specific mushroom
            target_id = event.mushroom_id
            if target_id is not None and target_id == mushroom.id:
                self._resistance[mushroom.id] = event.data.get("resistance", 0.5)
            elif target_id is None:
                # Global bio event - apply to all
                self._resistance[mushroom.id] = event.data.get("resistance", 0.5)
