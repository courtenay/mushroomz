"""Global modulation effects - LFOs and one-shot effects.

Provides a post-processing layer that applies modulation effects on top of
any active scene. Supports LFO modulation (sine/square/triangle) on
hue/saturation/brightness, and one-shot effects like flashes and color shifts.
"""

import math
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from fixtures.rgb_par import Color
from events import EventBus, Event, EventType


class LFOWaveform(Enum):
    """Available LFO waveforms."""
    OFF = auto()
    SINE = auto()
    SQUARE = auto()
    TRIANGLE = auto()


class LFOTarget(Enum):
    """What the LFO modulates."""
    HUE = auto()
    SATURATION = auto()
    BRIGHTNESS = auto()


@dataclass
class OneShotEffect:
    """A decaying one-shot effect."""
    effect_type: str  # "flash", "hue_shift", "pulse"
    intensity: float  # Current intensity (decays over time)
    decay_rate: float  # Units per second
    params: dict[str, Any] = field(default_factory=dict)


class Modulator:
    """Global modulation layer that applies on top of any scene.

    PS4 Button Mapping:
    - L2 (axis 4): LFO depth control (analog)
    - R2 (axis 5): LFO speed/frequency control (analog)
    - L3 (button 10): Cycle LFO target (Hue -> Sat -> Brightness)
    - R3 (button 11): Cycle LFO waveform (Sine -> Square -> Triangle -> Off)
    - Share (button 8): One-shot white flash
    - Touchpad (button 13): One-shot hue shift (180 degrees)
    """

    def __init__(self, event_bus: EventBus) -> None:
        self.event_bus = event_bus

        # LFO state
        self._lfo_waveform = LFOWaveform.OFF
        self._lfo_target = LFOTarget.HUE
        self._lfo_phase = 0.0  # 0-1, cycles continuously
        self._lfo_frequency = 0.5  # Hz (cycles per second)
        self._lfo_depth = 0.5  # 0-1, how much effect

        # One-shot effects queue
        self._one_shots: list[OneShotEffect] = []

        # History buffer for visualization (last N samples)
        self._history_size = 100  # 10 seconds at 10 FPS polling
        self._rgb_history: list[dict[str, list[int]]] = []

        # State for API exposure
        self._current_modulation = 0.0  # -1 to 1, current LFO value

        # Stick modulation state (applied on top of LFO)
        self._stick_hue_offset = 0.0  # Left stick X: -1 to 1 → -60 to +60 degrees
        self._stick_saturation_offset = 0.0  # Left stick Y: -1 to 1 → -0.5 to +0.5
        self._stick_brightness_offset = 0.0  # Right stick Y: -1 to 1 → -0.5 to +0.5

        # Subscribe to controller events
        event_bus.subscribe(EventType.CONTROLLER_BUTTON, self._handle_button)
        event_bus.subscribe(EventType.CONTROLLER_AXIS, self._handle_axis)
        event_bus.subscribe(EventType.LEAP_GESTURE, self._handle_gesture)

    def _handle_button(self, event: Event) -> None:
        """Handle controller buttons for modulation control."""
        button = event.data.get("button")
        pressed = event.data.get("pressed", False)

        if not pressed:
            return

        # L3 (10): Cycle LFO target
        if button == 10:
            targets = list(LFOTarget)
            idx = targets.index(self._lfo_target)
            self._lfo_target = targets[(idx + 1) % len(targets)]
            print(f"LFO Target: {self._lfo_target.name}")

        # R3 (11): Cycle LFO waveform
        elif button == 11:
            waveforms = list(LFOWaveform)
            idx = waveforms.index(self._lfo_waveform)
            self._lfo_waveform = waveforms[(idx + 1) % len(waveforms)]
            print(f"LFO Waveform: {self._lfo_waveform.name}")

        # Share (8): White flash one-shot
        elif button == 8:
            self._one_shots.append(OneShotEffect(
                effect_type="flash",
                intensity=1.0,
                decay_rate=3.0,
                params={"color": [255, 255, 255]}
            ))

        # Touchpad (13): Hue invert one-shot
        elif button == 13:
            self._one_shots.append(OneShotEffect(
                effect_type="hue_shift",
                intensity=1.0,
                decay_rate=2.0,
                params={"shift": 180}
            ))

    def _handle_axis(self, event: Event) -> None:
        """Handle analog axes for modulation control.

        Stick Mapping (global modulation on any scene):
        - Left stick X (axis 0): Hue offset ±60°
        - Left stick Y (axis 1): Saturation offset ±0.5
        - Right stick Y (axis 3): Brightness offset ±0.5

        Trigger Mapping (LFO control):
        - L2 (axis 4): LFO depth
        - R2 (axis 5): LFO frequency
        """
        axis = event.data.get("axis")
        value = event.data.get("value", 0.0)

        # Left stick X (axis 0): Hue offset
        if axis == 0:
            self._stick_hue_offset = value  # -1 to 1

        # Left stick Y (axis 1): Saturation offset (inverted - up is positive)
        elif axis == 1:
            self._stick_saturation_offset = -value  # Invert so up = more saturation

        # Right stick Y (axis 3): Brightness offset (inverted - up is positive)
        elif axis == 3:
            self._stick_brightness_offset = -value  # Invert so up = brighter

        # L2 (axis 4): LFO depth (triggers are -1 to 1, map to 0-1)
        elif axis == 4:
            self._lfo_depth = (value + 1) / 2

        # R2 (axis 5): LFO frequency (0.1 to 5 Hz)
        elif axis == 5:
            self._lfo_frequency = 0.1 + ((value + 1) / 2) * 4.9

    def _handle_gesture(self, event: Event) -> None:
        """Handle Leap Motion gestures for modulation control.

        Gesture Mapping:
        - GRAB: Trigger white flash
        - RELEASE: Trigger hue invert
        - TAP: Trigger color pulse
        - SWIPE_LEFT/RIGHT: Cycle LFO waveform
        - SWIPE_UP/DOWN: Cycle LFO target
        - CIRCLE_CW: Increase LFO frequency
        - CIRCLE_CCW: Decrease LFO frequency
        - PUSH: Increase LFO depth
        - PULL: Decrease LFO depth
        """
        gesture = event.data.get("gesture", "")
        strength = event.data.get("strength", 1.0)

        # GRAB: White flash
        if gesture == "GRAB":
            self._one_shots.append(OneShotEffect(
                effect_type="flash",
                intensity=strength,
                decay_rate=4.0,
                params={"color": [255, 255, 255]}
            ))

        # RELEASE: Hue invert
        elif gesture == "RELEASE":
            self._one_shots.append(OneShotEffect(
                effect_type="hue_shift",
                intensity=strength,
                decay_rate=2.0,
                params={"shift": 180}
            ))

        # TAP: Color pulse (random warm color)
        elif gesture == "TAP":
            import random
            hue = random.choice([0, 30, 60, 280, 320])  # Red, orange, yellow, purple, magenta
            color = self._hsv_to_rgb(hue, 1.0, 1.0)
            self._one_shots.append(OneShotEffect(
                effect_type="flash",
                intensity=strength,
                decay_rate=5.0,
                params={"color": color}
            ))

        # SWIPE_LEFT/RIGHT: Cycle LFO waveform
        elif gesture == "SWIPE_LEFT":
            waveforms = list(LFOWaveform)
            idx = waveforms.index(self._lfo_waveform)
            self._lfo_waveform = waveforms[(idx - 1) % len(waveforms)]
            print(f"LFO Waveform: {self._lfo_waveform.name}")

        elif gesture == "SWIPE_RIGHT":
            waveforms = list(LFOWaveform)
            idx = waveforms.index(self._lfo_waveform)
            self._lfo_waveform = waveforms[(idx + 1) % len(waveforms)]
            print(f"LFO Waveform: {self._lfo_waveform.name}")

        # SWIPE_UP/DOWN: Cycle LFO target
        elif gesture == "SWIPE_UP":
            targets = list(LFOTarget)
            idx = targets.index(self._lfo_target)
            self._lfo_target = targets[(idx + 1) % len(targets)]
            print(f"LFO Target: {self._lfo_target.name}")

        elif gesture == "SWIPE_DOWN":
            targets = list(LFOTarget)
            idx = targets.index(self._lfo_target)
            self._lfo_target = targets[(idx - 1) % len(targets)]
            print(f"LFO Target: {self._lfo_target.name}")

        # CIRCLE_CW/CCW: Adjust LFO frequency
        elif gesture == "CIRCLE_CW":
            self._lfo_frequency = min(5.0, self._lfo_frequency * 1.5)
            print(f"LFO Frequency: {self._lfo_frequency:.2f} Hz")

        elif gesture == "CIRCLE_CCW":
            self._lfo_frequency = max(0.1, self._lfo_frequency / 1.5)
            print(f"LFO Frequency: {self._lfo_frequency:.2f} Hz")

        # PUSH/PULL: Adjust LFO depth
        elif gesture == "PUSH":
            self._lfo_depth = min(1.0, self._lfo_depth + 0.2)
            print(f"LFO Depth: {self._lfo_depth:.0%}")

        elif gesture == "PULL":
            self._lfo_depth = max(0.0, self._lfo_depth - 0.2)
            print(f"LFO Depth: {self._lfo_depth:.0%}")

    def _hsv_to_rgb(self, h: float, s: float, v: float) -> list[int]:
        """Convert HSV to RGB list for one-shot color."""
        h = h / 360.0
        if s == 0:
            r = g = b = int(v * 255)
            return [r, g, b]

        i = int(h * 6)
        f = h * 6 - i
        p = v * (1 - s)
        q = v * (1 - f * s)
        t = v * (1 - (1 - f) * s)

        i = i % 6
        if i == 0:
            r, g, b = v, t, p
        elif i == 1:
            r, g, b = q, v, p
        elif i == 2:
            r, g, b = p, v, t
        elif i == 3:
            r, g, b = p, q, v
        elif i == 4:
            r, g, b = t, p, v
        else:
            r, g, b = v, p, q

        return [int(r * 255), int(g * 255), int(b * 255)]

    def _compute_lfo_value(self) -> float:
        """Compute current LFO value (-1 to 1)."""
        if self._lfo_waveform == LFOWaveform.OFF:
            return 0.0

        phase = self._lfo_phase

        if self._lfo_waveform == LFOWaveform.SINE:
            return math.sin(phase * 2 * math.pi)
        elif self._lfo_waveform == LFOWaveform.SQUARE:
            return 1.0 if phase < 0.5 else -1.0
        elif self._lfo_waveform == LFOWaveform.TRIANGLE:
            if phase < 0.25:
                return phase * 4
            elif phase < 0.75:
                return 1 - (phase - 0.25) * 4
            else:
                return -1 + (phase - 0.75) * 4
        return 0.0

    def _rgb_to_hsv(self, r: int, g: int, b: int) -> tuple[float, float, float]:
        """Convert RGB (0-255) to HSV (h: 0-360, s: 0-1, v: 0-1)."""
        r_norm, g_norm, b_norm = r / 255, g / 255, b / 255
        max_c = max(r_norm, g_norm, b_norm)
        min_c = min(r_norm, g_norm, b_norm)
        delta = max_c - min_c

        # Value
        v = max_c

        # Saturation
        s = 0.0 if max_c == 0 else delta / max_c

        # Hue
        if delta == 0:
            h = 0.0
        elif max_c == r_norm:
            h = 60 * (((g_norm - b_norm) / delta) % 6)
        elif max_c == g_norm:
            h = 60 * ((b_norm - r_norm) / delta + 2)
        else:
            h = 60 * ((r_norm - g_norm) / delta + 4)

        return h, s, v

    def update(self, dt: float) -> None:
        """Update LFO phase and decay one-shots."""
        # Advance LFO phase
        self._lfo_phase = (self._lfo_phase + dt * self._lfo_frequency) % 1.0
        self._current_modulation = self._compute_lfo_value() * self._lfo_depth

        # Decay one-shots
        active_effects = []
        for effect in self._one_shots:
            effect.intensity -= dt * effect.decay_rate
            if effect.intensity > 0:
                active_effects.append(effect)
        self._one_shots = active_effects

    def apply(self, color: Color) -> Color:
        """Apply modulation effects to a color."""
        # Convert to HSV for manipulation
        h, s, v = self._rgb_to_hsv(color.r, color.g, color.b)

        # Apply LFO modulation
        mod = self._current_modulation
        if self._lfo_target == LFOTarget.HUE:
            h = (h + mod * 60) % 360  # +/- 60 degrees
        elif self._lfo_target == LFOTarget.SATURATION:
            s = max(0, min(1, s + mod * 0.5))
        elif self._lfo_target == LFOTarget.BRIGHTNESS:
            v = max(0, min(1, v + mod * 0.5))

        # Apply stick modulation (additive on top of LFO)
        # Left stick X: Hue offset ±60 degrees
        h = (h + self._stick_hue_offset * 60) % 360
        # Left stick Y: Saturation offset ±0.5
        s = max(0, min(1, s + self._stick_saturation_offset * 0.5))
        # Right stick Y: Brightness offset ±0.5
        v = max(0, min(1, v + self._stick_brightness_offset * 0.5))

        # Apply one-shot effects
        flash_blend = 0.0
        flash_color = Color(255, 255, 255)
        hue_shift = 0.0

        for effect in self._one_shots:
            if effect.effect_type == "flash":
                flash_blend = max(flash_blend, effect.intensity)
                color_params = effect.params.get("color", [255, 255, 255])
                flash_color = Color(*color_params)
            elif effect.effect_type == "hue_shift":
                hue_shift += effect.params.get("shift", 0) * effect.intensity

        h = (h + hue_shift) % 360

        # Convert back to RGB
        result = Color.from_hsv(h, s, v)

        # Blend with flash if active
        if flash_blend > 0:
            result = result.blend(flash_color, flash_blend)

        return result

    def record_sample(self, mushroom_colors: dict[int, tuple[int, int, int]]) -> None:
        """Record a sample for the RGB history visualization.

        Args:
            mushroom_colors: Dict mapping mushroom_id to (r, g, b) tuple
        """
        sample = {
            str(mid): list(rgb)
            for mid, rgb in mushroom_colors.items()
        }
        self._rgb_history.append(sample)
        if len(self._rgb_history) > self._history_size:
            self._rgb_history.pop(0)

    def trigger_oneshot(self, effect_type: str, intensity: float = 1.0,
                        decay_rate: float = 3.0, params: dict[str, Any] | None = None) -> None:
        """Manually trigger a one-shot effect (for API use)."""
        self._one_shots.append(OneShotEffect(
            effect_type=effect_type,
            intensity=intensity,
            decay_rate=decay_rate,
            params=params or {}
        ))

    def set_lfo(self, waveform: str | None = None, target: str | None = None,
                frequency: float | None = None, depth: float | None = None) -> None:
        """Update LFO settings (for API use)."""
        if waveform is not None:
            self._lfo_waveform = LFOWaveform[waveform.upper()]
        if target is not None:
            self._lfo_target = LFOTarget[target.upper()]
        if frequency is not None:
            self._lfo_frequency = frequency
        if depth is not None:
            self._lfo_depth = depth

    def get_state(self) -> dict[str, Any]:
        """Get current modulator state for API."""
        return {
            "lfo": {
                "waveform": self._lfo_waveform.name,
                "target": self._lfo_target.name,
                "frequency": self._lfo_frequency,
                "depth": self._lfo_depth,
                "value": self._current_modulation,
                "phase": self._lfo_phase,
            },
            "stick": {
                "hue_offset": self._stick_hue_offset,
                "saturation_offset": self._stick_saturation_offset,
                "brightness_offset": self._stick_brightness_offset,
            },
            "one_shots": [
                {"type": e.effect_type, "intensity": e.intensity}
                for e in self._one_shots
            ],
            "rgb_history": self._rgb_history,
        }
