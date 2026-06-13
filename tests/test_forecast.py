"""
Integration tests for forecast.py — hit real APIs, check response structure.
These tests require an internet connection.
"""
import pytest
from helpers import DUBLIN_COORDS
from weathermap import forecast


class TestGetForecast:
    def test_returns_current_weather(self):
        data = forecast.getForecast(DUBLIN_COORDS)
        assert "current_weather" in data

    def test_current_weather_has_required_keys(self):
        data = forecast.getForecast(DUBLIN_COORDS)
        cw = data["current_weather"]
        for key in ("temperature", "windspeed", "winddirection", "weathercode", "is_day", "time"):
            assert key in cw, f"missing key: {key}"

    def test_hourly_data_present(self):
        data = forecast.getForecast(DUBLIN_COORDS)
        assert "hourly" in data
        hourly = data["hourly"]
        for key in ("temperature_2m", "weathercode", "precipitation_probability",
                    "uv_index", "is_day", "relativehumidity_2m", "cloudcover",
                    "windspeed_10m"):
            assert key in hourly, f"missing hourly key: {key}"

    def test_hourly_units_present(self):
        data = forecast.getForecast(DUBLIN_COORDS)
        assert "hourly_units" in data
        for key in ("temperature_2m", "precipitation_probability", "windspeed_10m",
                    "relativehumidity_2m"):
            assert key in data["hourly_units"], f"missing unit: {key}"

    def test_daily_data_present(self):
        data = forecast.getForecast(DUBLIN_COORDS)
        assert "daily" in data
        for key in ("sunrise", "sunset", "weathercode"):
            assert key in data["daily"], f"missing daily key: {key}"

    def test_temperature_is_plausible(self):
        data = forecast.getForecast(DUBLIN_COORDS)
        temp = data["current_weather"]["temperature"]
        assert -20 < temp < 45, f"temperature out of plausible range: {temp}"

    def test_weathercode_is_known(self):
        data = forecast.getForecast(DUBLIN_COORDS)
        code = data["current_weather"]["weathercode"]
        assert code in forecast.weather_codes, f"unknown weathercode: {code}"

    def test_forecast_days_coverage(self):
        data = forecast.getForecast(DUBLIN_COORDS)
        # 3 forecast days × 24 hours = 72 hourly entries
        assert len(data["hourly"]["temperature_2m"]) >= 72


class TestGetWeatherWarnings:
    def test_returns_list(self):
        result = forecast.getWeatherWarnings("Dublin")
        assert isinstance(result, list)

    def test_warning_structure_when_present(self):
        result = forecast.getWeatherWarnings("Dublin")
        for warning in result:
            for key in ("type", "level", "headline", "onset", "expiry"):
                assert key in warning, f"warning missing key: {key}"

    def test_all_irish_regions_have_fips_code(self):
        for region in forecast.weather_warning_regions_FIPS:
            code = forecast.weather_warning_regions_FIPS[region]
            assert code.startswith("EI"), f"{region} has unexpected FIPS code: {code}"


class TestWeatherCodes:
    def test_all_codes_have_day_and_night_icon(self):
        for code, entry in forecast.weather_codes.items():
            assert "day_icon" in entry, f"code {code} missing day_icon"
            assert "night_icon" in entry, f"code {code} missing night_icon"
            assert "desc" in entry, f"code {code} missing desc"

    def test_icon_filenames_are_strings(self):
        for code, entry in forecast.weather_codes.items():
            assert isinstance(entry["day_icon"], str)
            assert isinstance(entry["night_icon"], str)
            assert entry["day_icon"].endswith(".png")
            assert entry["night_icon"].endswith(".png")
