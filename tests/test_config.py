"""
Integration tests for config.py — attribute completeness and font loading.
"""
import pytest
from helpers import requires_assets
import config


class TestConfigAttributes:
    def test_required_user_settings_present(self):
        for attr in ("WEATHER_LOCATION", "MAP_COUNTRY", "SHOW_RADAR", "SHOW_FORECAST",
                     "SHOW_SIDEBAR", "SHOW_CURRENT_CONDITIONS", "SHOW_WARNINGS", "SUBTLE", "VCOM"):
            assert hasattr(config, attr), f"config missing: {attr}"

    def test_required_paths_present(self):
        for attr in ("font_path", "icon_path", "base_map_path", "weathermap_bmp_path",
                     "map_unit_shapefile_path", "radar_map_path", "pickle_path"):
            assert hasattr(config, attr), f"config missing: {attr}"

    def test_required_screen_settings_present(self):
        for attr in ("screen_width", "screen_height", "dpi", "sidebar_width",
                     "sidebar_height", "map_display_width"):
            assert hasattr(config, attr), f"config missing: {attr}"

    def test_map_display_width_is_correct(self):
        assert config.map_display_width == config.screen_width - config.sidebar_width

    def test_icon_sizes_are_tuples(self):
        for attr in ("SMALLER_ICON_SIZE", "ALMOST_SMALL_ICON_SIZE", "SMALL_ICON_SIZE",
                     "ALMOST_MED_ICON_SIZE", "MED_ICON_SIZE", "LARGE_ICON_SIZE"):
            val = getattr(config, attr)
            assert isinstance(val, tuple) and len(val) == 2, f"{attr} should be a 2-tuple"

    def test_map_settings_has_ireland(self):
        assert "Ireland" in config.map_settings

    def test_map_settings_ireland_has_required_keys(self):
        ireland = config.map_settings["Ireland"]
        for key in ("centre_lon", "centre_lat", "zoom", "extent", "focus_country_codes",
                    "non_focus_country_codes", "points_of_interest", "forecast_location", "tiles"):
            assert key in ireland, f"map_settings Ireland missing: {key}"

    def test_forecast_location_matches_forecast_locations(self):
        for country, settings in config.map_settings.items():
            loc = settings.get("forecast_location")
            if loc:
                assert loc in config.forecast_locations, (
                    f"forecast_location '{loc}' for {country} not in forecast_locations"
                )

    def test_weather_location_is_in_forecast_locations(self):
        assert config.WEATHER_LOCATION in config.forecast_locations

    def test_forecast_location_coords_are_valid(self):
        for name, loc in config.forecast_locations.items():
            lat, lon = loc["coords"]
            assert -90 <= lat <= 90, f"{name} latitude out of range: {lat}"
            assert -180 <= lon <= 180, f"{name} longitude out of range: {lon}"

    def test_urls_are_strings(self):
        for attr in ("open_meteo_url", "met_eireann_weather_warnings_url",
                     "rainviewer_timestamp_url", "rainviewer_radar_tile_url"):
            val = getattr(config, attr)
            assert isinstance(val, str) and val.startswith("https://"), f"{attr} looks wrong"


class TestFontLoading:
    @requires_assets
    def test_fonts_are_none_before_load(self):
        # Reset to None to simulate pre-load state
        import importlib
        importlib.reload(config)
        assert config.SMALL_FONT is None

    @requires_assets
    def test_load_fonts_sets_all_fonts(self):
        config.load_fonts()
        for attr in ("SMALLER_FONT", "SMALL_FONT", "MED_FONT", "LARGE_FONT",
                     "LARGER_FONT", "EXTRA_LARGE_FONT"):
            assert getattr(config, attr) is not None, f"{attr} is still None after load_fonts()"

    @requires_assets
    def test_load_fonts_is_idempotent(self):
        config.load_fonts()
        font_a = config.SMALL_FONT
        config.load_fonts()
        font_b = config.SMALL_FONT
        # Should produce equivalent font objects
        assert type(font_a) == type(font_b)
