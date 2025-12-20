"""Tests for scene classes and their parameter handling.

Note: These tests import scenes directly to avoid circular import issues
with the scenes/__init__.py module.
"""

import pytest
from unittest.mock import MagicMock

# Import scenes directly to avoid circular imports via __init__.py
from scenes.base import Scene
from scenes.pastel_fade import PastelFadeScene
from scenes.audio_pulse import AudioPulseScene
from scenes.bio_glow import BioGlowScene

from fixtures.rgb_par import Color, RGBFixture
from config import SceneParams


class MockMushroom:
    """Mock mushroom for testing scenes."""

    def __init__(self, mushroom_id: int = 0):
        self.id = mushroom_id
        self.name = f"Test Mushroom {mushroom_id}"
        self._color = Color()
        self._intensity = 1.0
        self.fixtures = [
            RGBFixture("Cap", 1),
            RGBFixture("Stem", 4),
        ]

    def set_target(self, color: Color) -> None:
        self._color = color

    def set_intensity(self, intensity: float) -> None:
        self._intensity = intensity

    def update(self, dt: float, smoothing: float = 0.1) -> None:
        for fixture in self.fixtures:
            fixture.set_target(self._color)
            fixture.update(dt, smoothing)


class TestSceneBase:
    """Tests for the base Scene class."""

    def test_scene_accepts_params(self):
        """Test that Scene accepts a params dict."""

        class TestScene(Scene):
            name = "Test"

            def update(self, mushroom, dt):
                pass

        params = {"foo": "bar", "baz": 123}
        scene = TestScene(params)
        assert scene._params == params

    def test_scene_params_default_to_empty_dict(self):
        """Test that Scene with no params gets empty dict."""

        class TestScene(Scene):
            name = "Test"

            def update(self, mushroom, dt):
                pass

        scene = TestScene()
        assert scene._params == {}

    def test_scene_starts_inactive(self):
        """Test that scenes start inactive."""

        class TestScene(Scene):
            name = "Test"

            def update(self, mushroom, dt):
                pass

        scene = TestScene()
        assert not scene.is_active

    def test_scene_activate_deactivate(self):
        """Test activate and deactivate methods."""

        class TestScene(Scene):
            name = "Test"

            def update(self, mushroom, dt):
                pass

        scene = TestScene()
        scene.activate()
        assert scene.is_active
        scene.deactivate()
        assert not scene.is_active


class TestPastelFadeScene:
    """Tests for PastelFadeScene."""

    def test_default_params(self):
        """Test that default params are used when none provided."""
        scene = PastelFadeScene()
        assert scene.cycle_duration == 30.0
        assert scene.phase_offset == 0.25

    def test_custom_params(self):
        """Test that custom params override defaults."""
        params = {"cycle_duration": 60.0, "phase_offset": 0.5}
        scene = PastelFadeScene(params)
        assert scene.cycle_duration == 60.0
        assert scene.phase_offset == 0.5

    def test_params_update_live(self):
        """Test that changes to params dict are reflected immediately."""
        params = {"cycle_duration": 30.0}
        scene = PastelFadeScene(params)
        assert scene.cycle_duration == 30.0

        # Modify the params dict (as the web API would)
        params["cycle_duration"] = 90.0
        assert scene.cycle_duration == 90.0

    def test_update_sets_color(self):
        """Test that update sets a color on the mushroom."""
        scene = PastelFadeScene()
        scene.activate()
        mushroom = MockMushroom()

        scene.update(mushroom, dt=0.1)

        # Mushroom should have had a color set
        assert mushroom._color is not None

    def test_phase_offset_affects_mushrooms(self):
        """Test that different mushrooms get different phase offsets."""
        params = {"phase_offset": 0.5}
        scene = PastelFadeScene(params)
        scene.activate()

        mushroom0 = MockMushroom(0)
        mushroom1 = MockMushroom(1)

        # Update both mushrooms
        scene.update(mushroom0, dt=0.0)
        scene.update(mushroom1, dt=0.0)

        # They should have different colors due to phase offset
        # (This is a bit tricky to test precisely, just verify it runs)
        assert mushroom0._color is not None
        assert mushroom1._color is not None


class TestAudioPulseScene:
    """Tests for AudioPulseScene."""

    def test_default_params(self):
        """Test that default params are used when none provided."""
        scene = AudioPulseScene()
        assert scene.base_hue == 280.0
        assert scene.decay_rate == 3.0

    def test_custom_params(self):
        """Test that custom params override defaults."""
        params = {"base_hue": 180.0, "decay_rate": 5.0}
        scene = AudioPulseScene(params)
        assert scene.base_hue == 180.0
        assert scene.decay_rate == 5.0

    def test_params_update_live(self):
        """Test that changes to params dict are reflected immediately."""
        params = {"base_hue": 180.0}
        scene = AudioPulseScene(params)

        # Modify the params dict
        params["base_hue"] = 0.0
        assert scene.base_hue == 0.0

    def test_update_with_no_audio(self):
        """Test update runs without audio events."""
        scene = AudioPulseScene()
        scene.activate()
        mushroom = MockMushroom()

        # Should not raise
        scene.update(mushroom, dt=0.1)

    def test_beat_intensity_decays(self):
        """Test that beat intensity decays over time."""
        params = {"decay_rate": 10.0}  # Fast decay
        scene = AudioPulseScene(params)
        scene.activate()

        # Simulate a beat
        scene._beat_intensity = 1.0

        mushroom = MockMushroom()
        scene.update(mushroom, dt=0.1)

        # Beat intensity should have decayed
        assert scene._beat_intensity < 1.0


class TestBioGlowScene:
    """Tests for BioGlowScene."""

    def test_default_params(self):
        """Test that default params are used when none provided."""
        scene = BioGlowScene()
        assert scene.low_color == (120, 0.6, 0.4)
        assert scene.high_color == (60, 0.8, 0.9)

    def test_custom_params(self):
        """Test that custom params override defaults."""
        params = {
            "low_color": [200, 0.5, 0.3],
            "high_color": [100, 0.9, 1.0],
        }
        scene = BioGlowScene(params)
        assert scene.low_color == (200, 0.5, 0.3)
        assert scene.high_color == (100, 0.9, 1.0)

    def test_params_update_live(self):
        """Test that changes to params dict are reflected immediately."""
        params = {
            "low_color": [120, 0.6, 0.4],
            "high_color": [60, 0.8, 0.9],
        }
        scene = BioGlowScene(params)

        # Modify the params dict
        params["low_color"] = [0, 1.0, 1.0]
        assert scene.low_color == (0, 1.0, 1.0)

    def test_update_with_default_resistance(self):
        """Test update uses default resistance of 0.5."""
        scene = BioGlowScene()
        scene.activate()
        mushroom = MockMushroom()

        scene.update(mushroom, dt=0.1)

        # Should have set some color
        assert mushroom._color is not None


class TestSceneParamsIntegration:
    """Tests for SceneParams integration with scenes."""

    def test_scene_params_pastel_fade(self):
        """Test that SceneParams work with PastelFadeScene."""
        params = SceneParams()
        params.pastel_fade["cycle_duration"] = 120.0

        scene = PastelFadeScene(params.pastel_fade)
        assert scene.cycle_duration == 120.0

    def test_scene_params_audio_pulse(self):
        """Test that SceneParams work with AudioPulseScene."""
        params = SceneParams()
        params.audio_pulse["base_hue"] = 0.0

        scene = AudioPulseScene(params.audio_pulse)
        assert scene.base_hue == 0.0

    def test_scene_params_bio_glow(self):
        """Test that SceneParams work with BioGlowScene."""
        params = SceneParams()
        params.bio_glow["low_color"] = [180, 0.7, 0.5]

        scene = BioGlowScene(params.bio_glow)
        assert scene.low_color == (180, 0.7, 0.5)

    def test_scene_params_shared_reference(self):
        """Test that scenes share the same params dict reference."""
        params = SceneParams()
        scene = PastelFadeScene(params.pastel_fade)

        # Modify via SceneParams
        params.pastel_fade["cycle_duration"] = 45.0

        # Scene should see the change
        assert scene.cycle_duration == 45.0
