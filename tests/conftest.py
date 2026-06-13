import argparse
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from helpers import DUBLIN_COORDS


@pytest.fixture
def build_args():
    """Minimal args for builder.build() — radar off for speed."""
    return argparse.Namespace(
        weather_location="Dublin",
        map_country="Ireland",
        radar=False,
        forecast=True,
        sidebar=True,
        current_conditions=True,
        warnings=True,
        subtle=True,
        custom_coords="",
    )


@pytest.fixture
def build_args_with_radar(build_args):
    build_args.radar = True
    return build_args
