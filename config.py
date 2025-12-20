"""Configuration for the mushroom lighting system."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FixtureConfig:
    """Configuration for a single DMX fixture."""
    name: str
    address: int  # DMX start address (1-512)
    channels: int = 3  # RGB = 3, RGBW = 4

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "address": self.address, "channels": self.channels}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FixtureConfig":
        return cls(
            name=data["name"],
            address=data["address"],
            channels=data.get("channels", 3),
        )


@dataclass
class MushroomConfig:
    """Configuration for a mushroom and its fixtures."""
    name: str
    fixtures: list[FixtureConfig] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "fixtures": [f.to_dict() for f in self.fixtures],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MushroomConfig":
        return cls(
            name=data["name"],
            fixtures=[FixtureConfig.from_dict(f) for f in data.get("fixtures", [])],
        )


@dataclass
class SceneParams:
    """Parameters for scene customization."""
    pastel_fade: dict[str, Any] = field(default_factory=lambda: {
        "cycle_duration": 30.0,
        "phase_offset": 0.25,
    })
    audio_pulse: dict[str, Any] = field(default_factory=lambda: {
        "base_hue": 280.0,
        "decay_rate": 3.0,
    })
    bio_glow: dict[str, Any] = field(default_factory=lambda: {
        "low_color": [120, 0.6, 0.4],
        "high_color": [60, 0.8, 0.9],
    })
    manual: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pastel_fade": self.pastel_fade,
            "audio_pulse": self.audio_pulse,
            "bio_glow": self.bio_glow,
            "manual": self.manual,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SceneParams":
        params = cls()
        if "pastel_fade" in data:
            params.pastel_fade.update(data["pastel_fade"])
        if "audio_pulse" in data:
            params.audio_pulse.update(data["audio_pulse"])
        if "bio_glow" in data:
            params.bio_glow.update(data["bio_glow"])
        if "manual" in data:
            params.manual.update(data["manual"])
        return params


@dataclass
class Config:
    """Main configuration."""
    # Art-Net settings
    artnet_ip: str = "169.254.219.50"  # DMX-USB controller
    artnet_universe: int = 0
    dmx_fps: int = 40  # DMX refresh rate

    # OSC settings
    osc_port: int = 8000

    # Idle settings
    idle_timeout: float = 30.0  # Seconds before idle mode kicks in

    # Web server
    web_port: int = 8085

    # Mushrooms
    mushrooms: list[MushroomConfig] = field(default_factory=list)

    # Scene parameters
    scene_params: SceneParams = field(default_factory=SceneParams)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artnet_ip": self.artnet_ip,
            "artnet_universe": self.artnet_universe,
            "dmx_fps": self.dmx_fps,
            "osc_port": self.osc_port,
            "idle_timeout": self.idle_timeout,
            "web_port": self.web_port,
            "mushrooms": [m.to_dict() for m in self.mushrooms],
            "scene_params": self.scene_params.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Config":
        return cls(
            artnet_ip=data.get("artnet_ip", "169.254.219.50"),
            artnet_universe=data.get("artnet_universe", 0),
            dmx_fps=data.get("dmx_fps", 40),
            osc_port=data.get("osc_port", 8000),
            idle_timeout=data.get("idle_timeout", 30.0),
            web_port=data.get("web_port", 8080),
            mushrooms=[MushroomConfig.from_dict(m) for m in data.get("mushrooms", [])],
            scene_params=SceneParams.from_dict(data.get("scene_params", {})),
        )


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
