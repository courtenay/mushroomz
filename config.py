"""Configuration for the mushroom lighting system."""

from dataclasses import dataclass, field


@dataclass
class FixtureConfig:
    """Configuration for a single DMX fixture."""
    name: str
    address: int  # DMX start address (1-512)
    channels: int = 3  # RGB = 3, RGBW = 4


@dataclass
class MushroomConfig:
    """Configuration for a mushroom and its fixtures."""
    name: str
    fixtures: list[FixtureConfig] = field(default_factory=list)


@dataclass
class Config:
    """Main configuration."""
    # Art-Net settings
    artnet_ip: str = "255.255.255.255"  # Broadcast by default
    artnet_universe: int = 0
    dmx_fps: int = 40  # DMX refresh rate

    # OSC settings
    osc_port: int = 8000

    # Idle settings
    idle_timeout: float = 30.0  # Seconds before idle mode kicks in

    # Mushrooms
    mushrooms: list[MushroomConfig] = field(default_factory=list)


# Default configuration - 4 mushrooms with 3 RGB fixtures each
DEFAULT_CONFIG = Config(
    mushrooms=[
        MushroomConfig(
            name="Mushroom 1",
            fixtures=[
                FixtureConfig("M1 Cap", address=1),
                FixtureConfig("M1 Stem", address=4),
                FixtureConfig("M1 Spot", address=7),
            ]
        ),
        MushroomConfig(
            name="Mushroom 2",
            fixtures=[
                FixtureConfig("M2 Cap", address=10),
                FixtureConfig("M2 Stem", address=13),
                FixtureConfig("M2 Spot", address=16),
            ]
        ),
        MushroomConfig(
            name="Mushroom 3",
            fixtures=[
                FixtureConfig("M3 Cap", address=19),
                FixtureConfig("M3 Stem", address=22),
                FixtureConfig("M3 Spot", address=25),
            ]
        ),
        MushroomConfig(
            name="Mushroom 4",
            fixtures=[
                FixtureConfig("M4 Cap", address=28),
                FixtureConfig("M4 Stem", address=31),
                FixtureConfig("M4 Spot", address=34),
            ]
        ),
    ]
)
