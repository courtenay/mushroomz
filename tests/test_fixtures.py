"""Tests for fixtures including Color and RGBFixture."""

import pytest
from fixtures.rgb_par import Color, RGBFixture


class TestColor:
    """Tests for the Color dataclass."""

    def test_default_color_is_black(self):
        """Test that default color is black (0, 0, 0)."""
        color = Color()
        assert color.r == 0
        assert color.g == 0
        assert color.b == 0

    def test_create_color_with_values(self):
        """Test creating a color with specific RGB values."""
        color = Color(r=255, g=128, b=64)
        assert color.r == 255
        assert color.g == 128
        assert color.b == 64

    def test_color_values_clamped_to_255(self):
        """Test that color values above 255 are clamped."""
        color = Color(r=300, g=256, b=1000)
        assert color.r == 255
        assert color.g == 255
        assert color.b == 255

    def test_color_values_clamped_to_0(self):
        """Test that negative color values are clamped to 0."""
        color = Color(r=-10, g=-1, b=-100)
        assert color.r == 0
        assert color.g == 0
        assert color.b == 0

    def test_from_hsv_red(self):
        """Test creating red from HSV."""
        color = Color.from_hsv(h=0, s=1.0, v=1.0)
        assert color.r == 255
        assert color.g == 0
        assert color.b == 0

    def test_from_hsv_green(self):
        """Test creating green from HSV."""
        color = Color.from_hsv(h=120, s=1.0, v=1.0)
        assert color.r == 0
        assert color.g == 255
        assert color.b == 0

    def test_from_hsv_blue(self):
        """Test creating blue from HSV."""
        color = Color.from_hsv(h=240, s=1.0, v=1.0)
        assert color.r == 0
        assert color.g == 0
        assert color.b == 255

    def test_from_hsv_white(self):
        """Test creating white from HSV (saturation=0)."""
        color = Color.from_hsv(h=0, s=0, v=1.0)
        assert color.r == 255
        assert color.g == 255
        assert color.b == 255

    def test_from_hsv_black(self):
        """Test creating black from HSV (value=0)."""
        color = Color.from_hsv(h=180, s=1.0, v=0)
        assert color.r == 0
        assert color.g == 0
        assert color.b == 0

    def test_from_hsv_hue_wraps_at_360(self):
        """Test that hue values wrap around at 360."""
        color1 = Color.from_hsv(h=0, s=1.0, v=1.0)
        color2 = Color.from_hsv(h=360, s=1.0, v=1.0)
        assert color1.r == color2.r
        assert color1.g == color2.g
        assert color1.b == color2.b

    def test_from_hsv_yellow(self):
        """Test creating yellow from HSV."""
        color = Color.from_hsv(h=60, s=1.0, v=1.0)
        assert color.r == 255
        assert color.g == 255
        assert color.b == 0

    def test_from_hsv_cyan(self):
        """Test creating cyan from HSV."""
        color = Color.from_hsv(h=180, s=1.0, v=1.0)
        assert color.r == 0
        assert color.g == 255
        assert color.b == 255

    def test_from_hsv_magenta(self):
        """Test creating magenta from HSV."""
        color = Color.from_hsv(h=300, s=1.0, v=1.0)
        assert color.r == 255
        assert color.g == 0
        assert color.b == 255

    def test_scaled_by_half(self):
        """Test scaling a color by 50%."""
        color = Color(r=200, g=100, b=50)
        scaled = color.scaled(0.5)
        assert scaled.r == 100
        assert scaled.g == 50
        assert scaled.b == 25

    def test_scaled_by_zero(self):
        """Test scaling a color to zero (black)."""
        color = Color(r=255, g=255, b=255)
        scaled = color.scaled(0.0)
        assert scaled.r == 0
        assert scaled.g == 0
        assert scaled.b == 0

    def test_scaled_by_one(self):
        """Test scaling by 1.0 returns same values."""
        color = Color(r=100, g=150, b=200)
        scaled = color.scaled(1.0)
        assert scaled.r == 100
        assert scaled.g == 150
        assert scaled.b == 200

    def test_blend_with_other_color(self):
        """Test blending two colors at 50%."""
        color1 = Color(r=0, g=0, b=0)
        color2 = Color(r=100, g=200, b=100)
        blended = color1.blend(color2, 0.5)
        assert blended.r == 50
        assert blended.g == 100
        assert blended.b == 50

    def test_blend_amount_zero(self):
        """Test blending with amount=0 returns original color."""
        color1 = Color(r=100, g=100, b=100)
        color2 = Color(r=200, g=200, b=200)
        blended = color1.blend(color2, 0.0)
        assert blended.r == 100
        assert blended.g == 100
        assert blended.b == 100

    def test_blend_amount_one(self):
        """Test blending with amount=1 returns other color."""
        color1 = Color(r=100, g=100, b=100)
        color2 = Color(r=200, g=200, b=200)
        blended = color1.blend(color2, 1.0)
        assert blended.r == 200
        assert blended.g == 200
        assert blended.b == 200

    def test_to_dmx(self):
        """Test converting color to DMX values."""
        color = Color(r=255, g=128, b=64)
        dmx = color.to_dmx()
        assert dmx == [255, 128, 64]


class TestRGBFixture:
    """Tests for the RGBFixture class."""

    def test_create_fixture(self):
        """Test creating a basic RGB fixture."""
        fixture = RGBFixture(name="Test", address=1)
        assert fixture.name == "Test"
        assert fixture.address == 1
        assert fixture.channels == 3

    def test_create_fixture_with_custom_channels(self):
        """Test creating an RGBW fixture with 4 channels."""
        fixture = RGBFixture(name="RGBW", address=10, channels=4)
        assert fixture.channels == 4

    def test_initial_color_is_black(self):
        """Test that fixture starts with black color."""
        fixture = RGBFixture(name="Test", address=1)
        assert fixture.color.r == 0
        assert fixture.color.g == 0
        assert fixture.color.b == 0

    def test_initial_intensity_is_full(self):
        """Test that fixture starts at full intensity."""
        fixture = RGBFixture(name="Test", address=1)
        assert fixture.intensity == 1.0

    def test_set_color(self):
        """Test setting fixture color."""
        fixture = RGBFixture(name="Test", address=1)
        fixture.color = Color(r=255, g=0, b=0)
        assert fixture.color.r == 255

    def test_set_intensity(self):
        """Test setting fixture intensity."""
        fixture = RGBFixture(name="Test", address=1)
        fixture.intensity = 0.5
        assert fixture.intensity == 0.5

    def test_intensity_clamped_to_max(self):
        """Test that intensity above 1.0 is clamped."""
        fixture = RGBFixture(name="Test", address=1)
        fixture.intensity = 1.5
        assert fixture.intensity == 1.0

    def test_intensity_clamped_to_min(self):
        """Test that negative intensity is clamped to 0."""
        fixture = RGBFixture(name="Test", address=1)
        fixture.intensity = -0.5
        assert fixture.intensity == 0.0

    def test_set_target(self):
        """Test setting target color."""
        fixture = RGBFixture(name="Test", address=1)
        fixture.set_target(Color(r=100, g=100, b=100))
        # Color shouldn't change immediately without update
        assert fixture.color.r == 0

    def test_update_moves_toward_target(self):
        """Test that update moves color toward target."""
        fixture = RGBFixture(name="Test", address=1)
        fixture.set_target(Color(r=255, g=255, b=255))
        fixture.update(dt=1.0, smoothing=1.0)  # High smoothing for fast test
        # Should have moved toward white
        assert fixture.color.r > 0
        assert fixture.color.g > 0
        assert fixture.color.b > 0

    def test_get_dmx_values(self):
        """Test getting DMX values from fixture."""
        fixture = RGBFixture(name="Test", address=1)
        fixture.color = Color(r=255, g=128, b=64)
        values = fixture.get_dmx_values()
        assert values == [255, 128, 64]

    def test_get_dmx_values_with_intensity(self):
        """Test that DMX values are scaled by intensity."""
        fixture = RGBFixture(name="Test", address=1)
        fixture.color = Color(r=200, g=100, b=50)
        fixture.intensity = 0.5
        values = fixture.get_dmx_values()
        assert values == [100, 50, 25]

    def test_setting_color_also_sets_target(self):
        """Test that setting color property also sets target."""
        fixture = RGBFixture(name="Test", address=1)
        fixture.color = Color(r=100, g=100, b=100)
        # After update with high smoothing, should stay same (target = color)
        fixture.update(dt=1.0, smoothing=1.0)
        assert fixture.color.r == 100
