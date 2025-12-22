"""Launchpad Mini visualization modes.

Adds animated display modes to the Launchpad Mini:
- LFO waveform display
- RGB level meters
- Mushroom color preview
- Beat reactive flash
"""

import math
import time
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .launchpad import LaunchpadMini

from .launchpad import LaunchpadColor


class VizMode(Enum):
    """Available visualization modes."""
    OFF = auto()           # Normal scene control mode
    LFO_WAVE = auto()      # Scrolling LFO waveform
    RGB_METERS = auto()    # Vertical RGB level bars per mushroom
    MUSHROOM_COLORS = auto()  # Show current mushroom colors
    SPECTRUM = auto()      # Faux spectrum analyzer
    BEAT_PULSE = auto()    # Beat-reactive full grid pulse


# Map RGB values to nearest Launchpad color
# Launchpad Mini has limited palette, we'll approximate
def rgb_to_launchpad_color(r: int, g: int, b: int) -> int:
    """Convert RGB to nearest Launchpad color velocity."""
    # Normalize to 0-1
    r_n, g_n, b_n = r / 255, g / 255, b / 255

    # Simple mapping based on dominant channel
    max_val = max(r_n, g_n, b_n)
    if max_val < 0.1:
        return LaunchpadColor.OFF

    # Determine hue region
    if r_n > g_n and r_n > b_n:
        # Red dominant
        if g_n > 0.5 * r_n:
            return LaunchpadColor.AMBER if max_val > 0.5 else LaunchpadColor.AMBER_LOW
        return LaunchpadColor.RED_FULL if max_val > 0.5 else LaunchpadColor.RED
    elif g_n > r_n and g_n > b_n:
        # Green dominant
        if r_n > 0.5 * g_n:
            return LaunchpadColor.YELLOW if max_val > 0.5 else LaunchpadColor.YELLOW
        return LaunchpadColor.GREEN_FULL if max_val > 0.5 else LaunchpadColor.GREEN
    elif b_n > r_n and b_n > g_n:
        # Blue dominant
        if r_n > 0.3 * b_n:
            return LaunchpadColor.PURPLE
        return LaunchpadColor.BLUE
    else:
        # Mixed - white-ish
        if r_n > 0.7 and g_n > 0.7:
            return LaunchpadColor.YELLOW_FULL
        return LaunchpadColor.WHITE


def value_to_color(value: float, channel: str = 'w') -> int:
    """Convert 0-1 value to color based on channel."""
    if value < 0.1:
        return LaunchpadColor.OFF

    if channel == 'r':
        return LaunchpadColor.RED_FULL if value > 0.5 else LaunchpadColor.RED
    elif channel == 'g':
        return LaunchpadColor.GREEN_FULL if value > 0.5 else LaunchpadColor.GREEN
    elif channel == 'b':
        return LaunchpadColor.BLUE if value > 0.3 else LaunchpadColor.CYAN
    else:
        # White/intensity
        if value > 0.7:
            return LaunchpadColor.WHITE
        elif value > 0.4:
            return LaunchpadColor.AMBER
        else:
            return LaunchpadColor.AMBER_LOW


class LaunchpadVisualizer:
    """Manages visualization modes for Launchpad Mini."""

    def __init__(self, launchpad: "LaunchpadMini") -> None:
        self.launchpad = launchpad
        self.mode = VizMode.OFF
        self._last_update = 0.0
        self._frame_time = 1.0 / 30  # 30 FPS target

        # LFO wave state
        self._wave_buffer: list[float] = [0.0] * 8  # 8 columns of wave data
        self._wave_scroll_pos = 0.0

        # Beat state
        self._beat_intensity = 0.0
        self._beat_decay = 5.0  # Decay rate per second

        # Cached mushroom colors
        self._mushroom_colors: dict[int, tuple[int, int, int]] = {}

        # Spectrum fake data
        self._spectrum_values: list[float] = [0.0] * 8

    def set_mode(self, mode: VizMode) -> None:
        """Change visualization mode."""
        if mode != self.mode:
            self.mode = mode
            if self.launchpad.connected:
                self.launchpad.clear_all()
            print(f"Launchpad viz mode: {mode.name}")

    def cycle_mode(self) -> VizMode:
        """Cycle to next visualization mode."""
        modes = list(VizMode)
        idx = modes.index(self.mode)
        new_mode = modes[(idx + 1) % len(modes)]
        self.set_mode(new_mode)
        return new_mode

    def trigger_beat(self, intensity: float = 1.0) -> None:
        """Trigger a beat flash."""
        self._beat_intensity = max(self._beat_intensity, intensity)

    def update_mushroom_colors(self, colors: dict[int, tuple[int, int, int]]) -> None:
        """Update cached mushroom colors."""
        self._mushroom_colors = colors

    def update_lfo(self, phase: float, value: float, waveform: str) -> None:
        """Update LFO wave display data."""
        # Scroll the wave buffer
        self._wave_scroll_pos = phase

        # Generate wave shape for display
        for i in range(8):
            col_phase = (phase + i / 8) % 1.0
            if waveform == "SINE":
                self._wave_buffer[i] = math.sin(col_phase * 2 * math.pi)
            elif waveform == "SQUARE":
                self._wave_buffer[i] = 1.0 if col_phase < 0.5 else -1.0
            elif waveform == "TRIANGLE":
                if col_phase < 0.25:
                    self._wave_buffer[i] = col_phase * 4
                elif col_phase < 0.75:
                    self._wave_buffer[i] = 1 - (col_phase - 0.25) * 4
                else:
                    self._wave_buffer[i] = -1 + (col_phase - 0.75) * 4
            else:
                self._wave_buffer[i] = 0.0

    def update_spectrum(self, values: list[float]) -> None:
        """Update spectrum analyzer values (0-1 for 8 bands)."""
        for i, v in enumerate(values[:8]):
            # Smooth decay
            self._spectrum_values[i] = max(v, self._spectrum_values[i] * 0.85)

    def update(self, dt: float) -> None:
        """Update visualization (call from main loop)."""
        if self.mode == VizMode.OFF:
            return

        if not self.launchpad.connected:
            return

        # Rate limit updates
        now = time.time()
        if now - self._last_update < self._frame_time:
            return
        self._last_update = now

        # Decay beat intensity
        self._beat_intensity = max(0, self._beat_intensity - dt * self._beat_decay)

        # Render based on mode
        if self.mode == VizMode.LFO_WAVE:
            self._render_lfo_wave()
        elif self.mode == VizMode.RGB_METERS:
            self._render_rgb_meters()
        elif self.mode == VizMode.MUSHROOM_COLORS:
            self._render_mushroom_colors()
        elif self.mode == VizMode.SPECTRUM:
            self._render_spectrum()
        elif self.mode == VizMode.BEAT_PULSE:
            self._render_beat_pulse()

    def _render_lfo_wave(self) -> None:
        """Render scrolling LFO waveform."""
        for x in range(8):
            # Map wave value (-1 to 1) to y position (0-7)
            value = self._wave_buffer[x]
            y_center = int((value + 1) / 2 * 7)

            for y in range(8):
                if y == y_center:
                    self.launchpad.set_pad(x, y, LaunchpadColor.GREEN_FULL)
                elif abs(y - y_center) == 1:
                    self.launchpad.set_pad(x, y, LaunchpadColor.GREEN)
                else:
                    self.launchpad.set_pad(x, y, LaunchpadColor.OFF)

    def _render_rgb_meters(self) -> None:
        """Render vertical RGB meters for each mushroom."""
        # Use columns 0-1 for M0, 2-3 for M1, etc. (up to 4 mushrooms)
        mushroom_ids = sorted(self._mushroom_colors.keys())[:4]

        for i, mid in enumerate(mushroom_ids):
            r, g, b = self._mushroom_colors.get(mid, (0, 0, 0))

            # R column
            r_col = i * 2
            r_height = int(r / 255 * 8)
            for y in range(8):
                if y < r_height:
                    self.launchpad.set_pad(r_col, y, LaunchpadColor.RED_FULL)
                else:
                    self.launchpad.set_pad(r_col, y, LaunchpadColor.OFF)

            # G/B combined column (G bottom, B top)
            gb_col = i * 2 + 1
            g_height = int(g / 255 * 4)  # Bottom 4
            b_height = int(b / 255 * 4)  # Top 4
            for y in range(4):
                if y < g_height:
                    self.launchpad.set_pad(gb_col, y, LaunchpadColor.GREEN_FULL)
                else:
                    self.launchpad.set_pad(gb_col, y, LaunchpadColor.OFF)
            for y in range(4, 8):
                if y - 4 < b_height:
                    self.launchpad.set_pad(gb_col, y, LaunchpadColor.BLUE)
                else:
                    self.launchpad.set_pad(gb_col, y, LaunchpadColor.OFF)

    def _render_mushroom_colors(self) -> None:
        """Render each mushroom's color as a column."""
        mushroom_ids = sorted(self._mushroom_colors.keys())

        for x in range(8):
            if x < len(mushroom_ids):
                mid = mushroom_ids[x]
                r, g, b = self._mushroom_colors.get(mid, (0, 0, 0))
                color = rgb_to_launchpad_color(r, g, b)

                # Fill entire column with mushroom color
                for y in range(8):
                    self.launchpad.set_pad(x, y, color)
            else:
                # Empty column
                for y in range(8):
                    self.launchpad.set_pad(x, y, LaunchpadColor.OFF)

    def _render_spectrum(self) -> None:
        """Render faux spectrum analyzer."""
        for x in range(8):
            value = self._spectrum_values[x]
            height = int(value * 8)

            for y in range(8):
                if y < height:
                    # Color gradient: green -> yellow -> red
                    if y < 3:
                        color = LaunchpadColor.GREEN_FULL
                    elif y < 6:
                        color = LaunchpadColor.YELLOW
                    else:
                        color = LaunchpadColor.RED_FULL
                    self.launchpad.set_pad(x, y, color)
                else:
                    self.launchpad.set_pad(x, y, LaunchpadColor.OFF)

    def _render_beat_pulse(self) -> None:
        """Render beat-reactive full grid pulse."""
        if self._beat_intensity > 0.1:
            # Bright flash
            if self._beat_intensity > 0.7:
                color = LaunchpadColor.WHITE
            elif self._beat_intensity > 0.4:
                color = LaunchpadColor.AMBER_FULL
            else:
                color = LaunchpadColor.AMBER_LOW

            for y in range(8):
                for x in range(8):
                    self.launchpad.set_pad(x, y, color)
        else:
            # Fade to off
            for y in range(8):
                for x in range(8):
                    self.launchpad.set_pad(x, y, LaunchpadColor.OFF)
