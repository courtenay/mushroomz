"""Tests for the configuration module."""

import pytest
from config import (
    Config,
    FixtureConfig,
    MushroomConfig,
    SceneParams,
    DMXOutputConfig,
    DEFAULT_CONFIG,
)


class TestFixtureConfig:
    """Tests for FixtureConfig dataclass."""

    def test_create_rgb_fixture(self):
        """Test creating an RGB fixture with default channels."""
        fixture = FixtureConfig(name="Test", address=1)
        assert fixture.name == "Test"
        assert fixture.address == 1
        assert fixture.channels == 3

    def test_create_rgbw_fixture(self):
        """Test creating an RGBW fixture with 4 channels."""
        fixture = FixtureConfig(name="RGBW Light", address=10, channels=4)
        assert fixture.channels == 4

    def test_to_dict(self):
        """Test serialization to dictionary."""
        fixture = FixtureConfig(name="Cap", address=5, channels=3)
        data = fixture.to_dict()
        assert data == {"name": "Cap", "address": 5, "channels": 3}

    def test_from_dict(self):
        """Test deserialization from dictionary."""
        data = {"name": "Stem", "address": 8, "channels": 4}
        fixture = FixtureConfig.from_dict(data)
        assert fixture.name == "Stem"
        assert fixture.address == 8
        assert fixture.channels == 4

    def test_from_dict_default_channels(self):
        """Test that channels defaults to 3 if not specified."""
        data = {"name": "Light", "address": 1}
        fixture = FixtureConfig.from_dict(data)
        assert fixture.channels == 3


class TestMushroomConfig:
    """Tests for MushroomConfig dataclass."""

    def test_create_empty_mushroom(self):
        """Test creating a mushroom with no fixtures."""
        mushroom = MushroomConfig(name="Empty Mushroom")
        assert mushroom.name == "Empty Mushroom"
        assert mushroom.fixtures == []

    def test_create_mushroom_with_fixtures(self):
        """Test creating a mushroom with fixtures."""
        fixtures = [
            FixtureConfig("Cap", 1),
            FixtureConfig("Stem", 4),
        ]
        mushroom = MushroomConfig(name="Test Mushroom", fixtures=fixtures)
        assert len(mushroom.fixtures) == 2
        assert mushroom.fixtures[0].name == "Cap"

    def test_to_dict(self):
        """Test serialization to dictionary."""
        mushroom = MushroomConfig(
            name="M1",
            fixtures=[FixtureConfig("Cap", 1, 3)],
        )
        data = mushroom.to_dict()
        assert data["name"] == "M1"
        assert len(data["fixtures"]) == 1
        assert data["fixtures"][0]["address"] == 1

    def test_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            "name": "M2",
            "fixtures": [
                {"name": "Cap", "address": 10, "channels": 3},
                {"name": "Stem", "address": 13, "channels": 3},
            ],
        }
        mushroom = MushroomConfig.from_dict(data)
        assert mushroom.name == "M2"
        assert len(mushroom.fixtures) == 2
        assert mushroom.fixtures[1].address == 13


class TestSceneParams:
    """Tests for SceneParams dataclass."""

    def test_default_params(self):
        """Test default scene parameters."""
        params = SceneParams()
        assert params.pastel_fade["cycle_duration"] == 30.0
        assert params.pastel_fade["phase_offset"] == 0.25
        assert params.audio_pulse["base_hue"] == 280.0
        assert params.audio_pulse["decay_rate"] == 3.0
        assert params.bio_glow["low_color"] == [120, 0.6, 0.4]
        assert params.bio_glow["high_color"] == [60, 0.8, 0.9]

    def test_to_dict(self):
        """Test serialization to dictionary."""
        params = SceneParams()
        data = params.to_dict()
        assert "pastel_fade" in data
        assert "audio_pulse" in data
        assert "bio_glow" in data
        assert "manual" in data

    def test_from_dict_with_custom_values(self):
        """Test deserialization with custom values."""
        data = {
            "pastel_fade": {"cycle_duration": 60.0, "phase_offset": 0.5},
            "audio_pulse": {"base_hue": 180.0},
        }
        params = SceneParams.from_dict(data)
        # Custom values should be applied
        assert params.pastel_fade["cycle_duration"] == 60.0
        assert params.pastel_fade["phase_offset"] == 0.5
        assert params.audio_pulse["base_hue"] == 180.0
        # Default decay_rate should still be present
        assert params.audio_pulse["decay_rate"] == 3.0

    def test_params_are_mutable(self):
        """Test that params can be modified after creation."""
        params = SceneParams()
        params.pastel_fade["cycle_duration"] = 120.0
        assert params.pastel_fade["cycle_duration"] == 120.0


class TestDMXOutputConfig:
    """Tests for DMXOutputConfig dataclass."""

    def test_default_config(self):
        """Test default DMX output configuration."""
        config = DMXOutputConfig()
        assert config.output_type == "artnet"
        assert config.artnet_ip == "169.254.219.50"
        assert config.artnet_universe == 0
        assert config.usb_port == ""

    def test_to_dict(self):
        """Test serialization."""
        config = DMXOutputConfig(output_type="opendmx", usb_port="/dev/ttyUSB0")
        data = config.to_dict()
        assert data["output_type"] == "opendmx"
        assert data["usb_port"] == "/dev/ttyUSB0"

    def test_from_dict(self):
        """Test deserialization."""
        data = {
            "output_type": "multi",
            "artnet_ip": "10.0.0.1",
            "artnet_universe": 5,
            "usb_port": "/dev/cu.usbserial",
        }
        config = DMXOutputConfig.from_dict(data)
        assert config.output_type == "multi"
        assert config.artnet_ip == "10.0.0.1"
        assert config.artnet_universe == 5


class TestConfig:
    """Tests for the main Config dataclass."""

    def test_default_config(self):
        """Test that DEFAULT_CONFIG is properly set up."""
        assert len(DEFAULT_CONFIG.mushrooms) == 4
        assert DEFAULT_CONFIG.mushrooms[0].name == "Mushroom 1"

    def test_full_roundtrip(self, sample_config_dict):
        """Test full serialization/deserialization roundtrip."""
        config = Config.from_dict(sample_config_dict)

        # Verify loaded values
        assert config.artnet_ip == "192.168.1.100"
        assert config.artnet_universe == 1
        assert config.dmx_fps == 30
        assert len(config.mushrooms) == 2
        assert config.mushrooms[0].name == "Test Mushroom 1"
        assert len(config.mushrooms[0].fixtures) == 2

        # Scene params should be loaded
        assert config.scene_params.pastel_fade["cycle_duration"] == 45.0
        assert config.scene_params.audio_pulse["base_hue"] == 180.0

    def test_to_dict_contains_all_fields(self):
        """Test that to_dict includes all expected fields."""
        config = Config()
        data = config.to_dict()

        expected_keys = [
            "dmx_output",
            "artnet_ip",
            "artnet_universe",
            "dmx_fps",
            "osc_port",
            "idle_timeout",
            "web_port",
            "mushrooms",
            "scene_params",
        ]
        for key in expected_keys:
            assert key in data, f"Missing key: {key}"

    def test_legacy_config_without_dmx_output(self):
        """Test loading legacy config without dmx_output section."""
        legacy_data = {
            "artnet_ip": "10.0.0.50",
            "artnet_universe": 2,
            "mushrooms": [],
        }
        config = Config.from_dict(legacy_data)
        # Should create dmx_output from legacy artnet settings
        assert config.dmx_output.output_type == "artnet"
        assert config.dmx_output.artnet_ip == "10.0.0.50"
        assert config.dmx_output.artnet_universe == 2
