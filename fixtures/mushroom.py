"""Mushroom fixture group."""

from .rgb_par import RGBFixture, Color
from config import MushroomConfig


class Mushroom:
    """A mushroom with multiple fixtures."""

    def __init__(self, config: MushroomConfig, mushroom_id: int) -> None:
        self.id = mushroom_id
        self.name = config.name
        self.fixtures: list[RGBFixture] = []

        for fixture_config in config.fixtures:
            self.fixtures.append(
                RGBFixture(
                    name=fixture_config.name,
                    address=fixture_config.address,
                    channels=fixture_config.channels,
                )
            )

    def set_color(self, color: Color) -> None:
        """Set all fixtures to the same color."""
        for fixture in self.fixtures:
            fixture.color = color

    def set_target(self, color: Color) -> None:
        """Set target color for all fixtures."""
        for fixture in self.fixtures:
            fixture.set_target(color)

    def set_intensity(self, intensity: float) -> None:
        """Set intensity for all fixtures."""
        for fixture in self.fixtures:
            fixture.intensity = intensity

    def update(self, dt: float, smoothing: float = 0.1) -> None:
        """Update all fixtures."""
        for fixture in self.fixtures:
            fixture.update(dt, smoothing)

    def get_dmx_data(self) -> dict[int, list[int]]:
        """Get DMX data as {address: [values]} dict."""
        data = {}
        for fixture in self.fixtures:
            data[fixture.address] = fixture.get_dmx_values()
        return data
