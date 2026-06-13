"""Entry point. Builds the weathermap image and optionally sends it to the e-paper display."""
import argparse
import logging
import logging.handlers
import os
import sys

import config
from weathermap import builder


def setup_logging():
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "weathermap.log")

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    fmt = logging.Formatter("%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")

    # Rotate at 1 MB, keep 5 backups
    file_handler = logging.handlers.RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=5)
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(fmt)
    root.addHandler(stream_handler)


def parse_args():
    parser = argparse.ArgumentParser(description="Weathermap — radar + forecast for e-paper display")
    parser.add_argument("--weather-location", dest="weather_location", default=config.WEATHER_LOCATION)
    parser.add_argument("--map-country", dest="map_country", default=config.MAP_COUNTRY)
    parser.add_argument("--radar", dest="radar", action="store_true", default=config.SHOW_RADAR)
    parser.add_argument("--forecast", dest="forecast", action="store_true", default=config.SHOW_FORECAST)
    parser.add_argument("--sidebar", dest="sidebar", action="store_true", default=config.SHOW_SIDEBAR)
    parser.add_argument("--current-conditions", dest="current_conditions", action="store_true", default=config.SHOW_CURRENT_CONDITIONS)
    parser.add_argument("--warnings", dest="warnings", action="store_true", default=config.SHOW_WARNINGS)
    parser.add_argument("--subtle", dest="subtle", action="store_true", default=config.SUBTLE)
    parser.add_argument("--custom-coords", dest="custom_coords", default="")
    parser.add_argument(
        "--no-display",
        dest="no_display",
        action="store_true",
        default=False,
        help="Build image only, do not send to e-paper (useful for testing off-Pi)",
    )
    return parser.parse_args()


def main():
    setup_logging()
    logger = logging.getLogger(__name__)

    args = parse_args()
    try:
        image_path = builder.build(args)
    except Exception:
        logger.exception("Fatal error — could not build weathermap image")
        sys.exit(1)

    if not args.no_display:
        import send_to_display
        try:
            send_to_display.send(image_path, vcom=config.VCOM)
        except Exception:
            logger.exception("Failed to send image to display")
            sys.exit(1)


if __name__ == "__main__":
    main()
