"""RGB PAR fixture model."""

from dataclasses import dataclass


@dataclass
class Color:
    """RGB color with optional intensity."""
    r: int = 0
    g: int = 0
    b: int = 0

    def __post_init__(self) -> None:
        self.r = max(0, min(255, self.r))
        self.g = max(0, min(255, self.g))
        self.b = max(0, min(255, self.b))

    @classmethod
    def from_hsv(cls, h: float, s: float, v: float) -> "Color":
        """Create color from HSV values (h: 0-360, s: 0-1, v: 0-1)."""
        h = h % 360
        c = v * s
        x = c * (1 - abs((h / 60) % 2 - 1))
        m = v - c

        if h < 60:
            r, g, b = c, x, 0
        elif h < 120:
            r, g, b = x, c, 0
        elif h < 180:
            r, g, b = 0, c, x
        elif h < 240:
            r, g, b = 0, x, c
        elif h < 300:
            r, g, b = x, 0, c
        else:
            r, g, b = c, 0, x

        return cls(
            r=int((r + m) * 255),
            g=int((g + m) * 255),
            b=int((b + m) * 255),
        )

    def scaled(self, intensity: float) -> "Color":
        """Return a new color scaled by intensity (0-1)."""
        return Color(
            r=int(self.r * intensity),
            g=int(self.g * intensity),
            b=int(self.b * intensity),
        )

    def blend(self, other: "Color", amount: float) -> "Color":
        """Blend with another color (amount: 0=self, 1=other)."""
        return Color(
            r=int(self.r + (other.r - self.r) * amount),
            g=int(self.g + (other.g - self.g) * amount),
            b=int(self.b + (other.b - self.b) * amount),
        )

    def to_dmx(self) -> list[int]:
        """Convert to DMX channel values."""
        return [self.r, self.g, self.b]


class RGBFixture:
    """A single RGB PAR fixture."""

    def __init__(self, name: str, address: int, channels: int = 3) -> None:
        self.name = name
        self.address = address  # 1-indexed DMX address
        self.channels = channels
        self._color = Color()
        self._target_color = Color()
        self._intensity = 1.0

    @property
    def color(self) -> Color:
        return self._color

    @color.setter
    def color(self, value: Color) -> None:
        self._color = value
        self._target_color = value

    @property
    def intensity(self) -> float:
        return self._intensity

    @intensity.setter
    def intensity(self, value: float) -> None:
        self._intensity = max(0.0, min(1.0, value))

    def set_target(self, color: Color) -> None:
        """Set target color for smooth transitions."""
        self._target_color = color

    def update(self, dt: float, smoothing: float = 0.1) -> None:
        """Update color towards target with smoothing."""
        blend = min(1.0, smoothing * dt * 60)  # Normalize to ~60fps
        self._color = self._color.blend(self._target_color, blend)

    def get_dmx_values(self) -> list[int]:
        """Get DMX values for this fixture."""
        return self._color.scaled(self._intensity).to_dmx()
