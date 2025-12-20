"""Audio pulse scene - reactive to beat and audio levels."""

from .base import Scene
from fixtures.mushroom import Mushroom
from fixtures.rgb_par import Color
from events import Event, EventType


class AudioPulseScene(Scene):
    """Beat-reactive lighting scene."""

    name = "Audio Pulse"

    def __init__(self) -> None:
        super().__init__()
        self._beat_intensity = 0.0
        self._audio_level = 0.0
        self._low = 0.0
        self._mid = 0.0
        self._high = 0.0
        self._base_hue = 280.0  # Purple base
        self._decay_rate = 3.0  # How fast the beat effect fades

    def activate(self) -> None:
        super().activate()
        self._beat_intensity = 0.0
        self._audio_level = 0.0

    def update(self, mushroom: Mushroom, dt: float) -> None:
        # Decay beat intensity
        self._beat_intensity = max(0, self._beat_intensity - dt * self._decay_rate)

        # Mix base color with beat flash
        base_brightness = 0.3 + self._audio_level * 0.3
        beat_brightness = self._beat_intensity * 0.7

        # Shift hue based on frequency content
        hue_shift = self._low * 30 - self._high * 30
        hue = (self._base_hue + hue_shift) % 360

        # Higher saturation on beats
        saturation = 0.6 + self._beat_intensity * 0.4

        brightness = min(1.0, base_brightness + beat_brightness)
        color = Color.from_hsv(hue, saturation, brightness)

        mushroom.set_target(color)
        mushroom.update(dt, smoothing=0.3)  # Faster response

    def handle_event(self, event: Event, mushroom: Mushroom) -> None:
        if event.type == EventType.OSC_AUDIO_BEAT:
            self._beat_intensity = min(1.0, event.data.get("intensity", 1.0))
        elif event.type == EventType.OSC_AUDIO_LEVEL:
            self._audio_level = event.data.get("level", 0.0)
            self._low = event.data.get("low", 0.0)
            self._mid = event.data.get("mid", 0.0)
            self._high = event.data.get("high", 0.0)
