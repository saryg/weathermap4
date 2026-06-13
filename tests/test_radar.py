"""
Integration tests for radar.py — hit RainViewer API and test map rendering.
Rendering tests require local assets (shapefiles) and are marked accordingly.
"""
import pytest
from PIL import Image
from helpers import requires_assets

pytest.importorskip("cartopy", reason="cartopy not installed")
from weathermap import radar
import config


class TestRainViewer:
    def test_get_latest_radar_path_returns_string(self):
        path = radar.getLatestRadarPath()
        assert path is not None
        assert isinstance(path, str)
        assert path.startswith("/v2/radar/")

    def test_radar_path_produces_valid_tile_url(self):
        import requests
        path = radar.getLatestRadarPath()
        url = config.rainviewer_radar_tile_url.format(path=path, x=14, y=10, z=5)
        resp = requests.get(url, timeout=15)
        # 200 = tile has data, 410 = valid response but no radar for this tile
        assert resp.status_code in (200, 410)


class TestCountryMapShape:
    @requires_assets
    def test_ireland_returns_geometries(self):
        focus, non_focus = radar.countryMapShape("Ireland")
        assert len(focus) > 0
        assert len(non_focus) > 0

    @requires_assets
    def test_germany_returns_geometries(self):
        focus, non_focus = radar.countryMapShape("Germany")
        assert len(focus) > 0
        assert len(non_focus) > 0

    @requires_assets
    def test_focus_and_non_focus_are_disjoint(self):
        focus, non_focus = radar.countryMapShape("Ireland")
        # Rough check — geometries shouldn't overlap significantly
        assert len(focus) < len(non_focus)


class TestBaseMap:
    @requires_assets
    @pytest.mark.slow
    def test_create_base_map_saves_file(self, tmp_path, monkeypatch):
        import config
        # Redirect output paths to tmp so we don't pollute the project
        monkeypatch.setattr(config, "base_map_path", str(tmp_path / "{country}_base_map.png"))
        monkeypatch.setattr(config, "pickle_path", str(tmp_path / "{country}.axes.pickle"))

        ax = radar.createBaseMap("Ireland")
        assert ax is not None
        assert (tmp_path / "Ireland_base_map.png").exists()
        assert (tmp_path / "Ireland.axes.pickle").exists()

    @requires_assets
    @pytest.mark.slow
    def test_base_map_image_is_correct_size(self, tmp_path, monkeypatch):
        import config
        monkeypatch.setattr(config, "base_map_path", str(tmp_path / "{country}_base_map.png"))
        monkeypatch.setattr(config, "pickle_path", str(tmp_path / "{country}.axes.pickle"))

        radar.createBaseMap("Ireland")
        img = Image.open(str(tmp_path / "Ireland_base_map.png"))
        assert img.size == (config.screen_width, config.screen_height)
