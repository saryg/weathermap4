"""
Generate a demo weathermap image with a fake Status Orange wind warning.
Saves to images/demo_weathermap.png.

Usage (from project root, with venv active):
    python tools/make_demo.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch
from PIL import Image
import config
import weathermap.forecast as forecast
import weathermap.builder as builder
import argparse

FAKE_WARNING = [
    {
        "type": "Warning",
        "level": "Status Orange",
        "headline": "Wind Warning",
        "description": "Southwest winds reaching 110 km/h in exposed areas. Risk of structural damage.",
        "onset": "2026-06-14T18:00:00+01:00",
        "expiry": "2026-06-15T06:00:00+01:00",
        "regions": ["Dublin"],
    }
]


def main():
    args = argparse.Namespace(
        weather_location=config.WEATHER_LOCATION,
        map_country=config.MAP_COUNTRY,
        warnings=True,
        forecast=config.SHOW_FORECAST,
        sidebar=config.SHOW_SIDEBAR,
        current_conditions=config.SHOW_CURRENT_CONDITIONS,
        subtle=config.SUBTLE,
        radar=config.SHOW_RADAR,
    )

    with patch.object(forecast, "getWeatherWarnings", return_value=FAKE_WARNING):
        image_path = builder.build(args)

    demo_path = os.path.join(config.BASE_DIR, "images", "demo_weathermap.png")
    Image.open(image_path).save(demo_path)
    print(f"Saved demo to {demo_path}")


if __name__ == "__main__":
    main()
