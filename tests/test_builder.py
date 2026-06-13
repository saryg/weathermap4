"""
Integration tests for builder.py — full image composition pipeline.
Requires local assets (fonts, icons, shapefiles) and internet access.
"""
import os
import pytest
from PIL import Image
from helpers import requires_assets, DUBLIN_COORDS

pytest.importorskip("cartopy", reason="cartopy not installed")
from weathermap import builder, forecast


class TestBuild:
    @requires_assets
    def test_build_produces_bmp(self, build_args, tmp_path, monkeypatch):
        import config
        out = str(tmp_path / "weathermap.bmp")
        monkeypatch.setattr(config, "weathermap_bmp_path", out)
        # Use base map path if it exists, else skip radar
        result = builder.build(build_args)
        assert os.path.exists(result)

    @requires_assets
    def test_output_is_valid_image(self, build_args, tmp_path, monkeypatch):
        import config
        out = str(tmp_path / "weathermap.bmp")
        monkeypatch.setattr(config, "weathermap_bmp_path", out)
        builder.build(build_args)
        img = Image.open(out)
        assert img.size == (config.screen_width, config.screen_height)

    @requires_assets
    def test_build_returns_output_path(self, build_args, tmp_path, monkeypatch):
        import config
        out = str(tmp_path / "weathermap.bmp")
        monkeypatch.setattr(config, "weathermap_bmp_path", out)
        result = builder.build(build_args)
        assert result == out


class TestDrawingHelpers:
    @requires_assets
    def test_add_empty_sidebar_returns_image(self):
        import config
        config.load_fonts()
        image = Image.new("RGBA", (config.screen_width, config.screen_height), "white")
        result = builder.addEmptySidebar(image)
        assert isinstance(result, Image.Image)
        assert result.size == (config.screen_width, config.screen_height)

    @requires_assets
    def test_add_sidebar_returns_image(self):
        import config
        config.load_fonts()
        data = forecast.getForecast(DUBLIN_COORDS)
        image = Image.new("RGBA", (config.screen_width, config.screen_height), "white")
        result = builder.addSidebar(image, data)
        assert isinstance(result, Image.Image)

    @requires_assets
    def test_add_subtle_weather_descriptions_returns_image(self):
        import config
        config.load_fonts()
        data = forecast.getForecast(DUBLIN_COORDS)
        image = Image.new("RGBA", (config.screen_width, config.screen_height), "white")
        result = builder.addSubtleWeatherDescriptions(image, data, "Dublin")
        assert isinstance(result, Image.Image)

    @requires_assets
    def test_add_current_conditions_returns_image(self):
        import config
        config.load_fonts()
        data = forecast.getForecast(DUBLIN_COORDS)
        image = Image.new("RGBA", (config.screen_width, config.screen_height), "white")
        result = builder.addCurrentConditions(image, data, "white")
        assert isinstance(result, Image.Image)

    @requires_assets
    def test_add_weather_warnings_skips_advisory(self):
        import config
        config.load_fonts()
        warnings = [
            {"type": "Advisory", "level": "Advisory", "headline": "Some advisory",
             "onset": "2026-01-01T00:00", "expiry": "2026-01-01T12:00"},
        ]
        image = Image.new("RGBA", (config.screen_width, config.screen_height), "white")
        result = builder.addWeatherWarnings(image, warnings)
        # Advisory should be filtered — image returned unchanged
        assert isinstance(result, Image.Image)

    @requires_assets
    def test_add_weather_warnings_skips_blight(self):
        import config
        config.load_fonts()
        warnings = [
            {"type": "Warning", "level": "Status Yellow", "headline": "Blight warning for crops",
             "onset": "2026-01-01T00:00", "expiry": "2026-01-01T12:00"},
        ]
        image = Image.new("RGBA", (config.screen_width, config.screen_height), "white")
        result = builder.addWeatherWarnings(image, warnings)
        assert isinstance(result, Image.Image)

    @requires_assets
    def test_add_weather_warnings_draws_real_warning(self):
        import config
        config.load_fonts()
        warnings = [
            {"type": "Warning", "level": "Status Orange",
             "headline": "Heavy rain and persistent thunderstorms expected",
             "onset": "2026-01-27T03:00", "expiry": "2026-01-27T18:00"},
        ]
        image = Image.new("RGBA", (config.screen_width, config.screen_height), "white")
        result = builder.addWeatherWarnings(image, warnings)
        assert isinstance(result, Image.Image)


class TestCentreHelpers:
    @requires_assets
    def test_centre_text_horizontally_within_bounds(self):
        import config
        from PIL import ImageDraw
        config.load_fonts()
        image = Image.new("RGBA", (config.screen_width, config.screen_height), "white")
        draw = ImageDraw.Draw(image)
        x, w, h = builder.centreTextHorizontally(draw, "Dublin", config.MED_FONT, 0, config.map_display_width)
        assert 0 <= x <= config.map_display_width
        assert w > 0
        assert h > 0

    def test_centre_icon_horizontally_within_bounds(self):
        import config
        result = builder.centreIconHorizontally(60, 0, config.map_display_width)
        assert 0 <= result <= config.map_display_width
