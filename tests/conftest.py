"""Pytest configuration and fixtures for the lighting controller tests."""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest


@pytest.fixture
def sample_config_dict() -> dict:
    """Sample configuration dictionary for testing."""
    return {
        "artnet_ip": "192.168.1.100",
        "artnet_universe": 1,
        "dmx_fps": 30,
        "osc_port": 9000,
        "idle_timeout": 60.0,
        "web_port": 8080,
        "dmx_output": {
            "output_type": "artnet",
            "artnet_ip": "192.168.1.100",
            "artnet_universe": 1,
            "usb_port": "",
        },
        "mushrooms": [
            {
                "name": "Test Mushroom 1",
                "fixtures": [
                    {"name": "Cap", "address": 1, "channels": 3},
                    {"name": "Stem", "address": 4, "channels": 3},
                ],
            },
            {
                "name": "Test Mushroom 2",
                "fixtures": [
                    {"name": "Cap", "address": 10, "channels": 4},
                ],
            },
        ],
        "scene_params": {
            "pastel_fade": {"cycle_duration": 45.0, "phase_offset": 0.3},
            "audio_pulse": {"base_hue": 180.0, "decay_rate": 5.0},
            "bio_glow": {
                "low_color": [100, 0.5, 0.3],
                "high_color": [50, 0.9, 1.0],
            },
            "manual": {},
        },
    }


@pytest.fixture
def scene_params_dict() -> dict:
    """Scene parameters dictionary for testing."""
    return {
        "pastel_fade": {"cycle_duration": 60.0, "phase_offset": 0.5},
        "audio_pulse": {"base_hue": 300.0, "decay_rate": 2.0},
        "bio_glow": {
            "low_color": [120, 0.6, 0.4],
            "high_color": [60, 0.8, 0.9],
        },
        "manual": {},
    }
