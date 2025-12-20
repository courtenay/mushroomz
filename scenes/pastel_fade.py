"""Pastel fade scene - gentle color cycling through soft colors."""

import math

from .base import Scene
from fixtures.mushroom import Mushroom
from fixtures.rgb_par import Color
from events import Event


class PastelFadeScene(Scene):
    """Gentle pastel color fading - the default idle scene."""

    name = "Pastel Fade"

    # Pastel colors with soft saturation
    PASTELS = [
        (350, 0.35, 0.9),  # Soft pink
        (30, 0.40, 0.95),  # Peach
        (55, 0.35, 0.95),  # Soft yellow
        (140, 0.35, 0.85), # Mint
        (180, 0.35, 0.85), # Soft cyan
        (220, 0.35, 0.85), # Powder blue
        (270, 0.30, 0.85), # Lavender
        (320, 0.35, 0.85), # Soft magenta
    ]

    def __init__(self) -> None:
        super().__init__()
        self._phase: dict[int, float] = {}  # Per-mushroom phase offset
        self._time = 0.0
        self.cycle_duration = 30.0  # Seconds per full cycle
        self.phase_offset = 0.25  # Phase offset between mushrooms (fraction of cycle)

    def activate(self) -> None:
        super().activate()
        self._time = 0.0

    def update(self, mushroom: Mushroom, dt: float) -> None:
        self._time += dt

        # Get phase offset for this mushroom
        if mushroom.id not in self._phase:
            self._phase[mushroom.id] = mushroom.id * self.phase_offset

        # Calculate position in color cycle
        phase = self._phase[mushroom.id]
        cycle_pos = ((self._time / self.cycle_duration) + phase) % 1.0

        # Smooth interpolation between colors
        num_colors = len(self.PASTELS)
        color_index = cycle_pos * num_colors
        idx1 = int(color_index) % num_colors
        idx2 = (idx1 + 1) % num_colors
        blend = color_index - int(color_index)

        # Smooth blend using sine curve
        blend = (1 - math.cos(blend * math.pi)) / 2

        h1, s1, v1 = self.PASTELS[idx1]
        h2, s2, v2 = self.PASTELS[idx2]

        # Handle hue wrapping
        if abs(h2 - h1) > 180:
            if h1 > h2:
                h2 += 360
            else:
                h1 += 360

        h = (h1 + (h2 - h1) * blend) % 360
        s = s1 + (s2 - s1) * blend
        v = v1 + (v2 - v1) * blend

        color = Color.from_hsv(h, s, v)
        mushroom.set_target(color)
        mushroom.update(dt, smoothing=0.05)

    def handle_event(self, event: Event, mushroom: Mushroom) -> None:
        # Pastel scene ignores most events, staying calm
        pass
