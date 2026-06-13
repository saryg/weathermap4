import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

DUBLIN_COORDS = [53.3498, -6.2603]


def assets_present():
    root = os.path.join(os.path.dirname(__file__), "..")
    return all([
        os.path.exists(os.path.join(root, "fonts", "BebasNeue-Regular.ttf")),
        os.path.exists(os.path.join(root, "icons-transparent")),
        os.path.exists(os.path.join(root, "ne_10m_map_units", "ne_10m_admin_0_map_units.shp")),
    ])


requires_assets = pytest.mark.skipif(
    not assets_present(),
    reason="Local assets not present (fonts, icons, shapefiles)",
)
