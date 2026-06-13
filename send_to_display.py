"""
Send a BMP image to the Waveshare e-paper display via IT8951.
Runs only on Raspberry Pi — importing this module on other systems is safe;
the IT8951 dependency is loaded lazily at call time.
"""
import argparse


def _it8951():
    """Import IT8951 lazily, raising a clear RuntimeError if not installed."""
    try:
        from IT8951.display import AutoEPDDisplay
        from IT8951.functions import display_image, clear_display
        return AutoEPDDisplay, display_image, clear_display
    except ImportError:
        raise RuntimeError(
            "IT8951 not available. Are you running on a Raspberry Pi with IT8951 installed?\n"
            "  pip install IT8951\n"
            "Run with --no-display to skip sending to the screen."
        )


def send(image_path, vcom=-2.15, rotate="CCW"):
    AutoEPDDisplay, display_image, _ = _it8951()
    display = AutoEPDDisplay(vcom=vcom, rotate=rotate, mirror=False, spi_hz=24000000)
    print("VCOM set to", display.epd.get_vcom())
    display_image(image_path, display)
    print("Done.")


def clear(vcom=-2.15, rotate="CCW"):
    AutoEPDDisplay, _, clear_display = _it8951()
    display = AutoEPDDisplay(vcom=vcom, rotate=rotate, mirror=False, spi_hz=24000000)
    clear_display(display)
    print("Display cleared.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Send a BMP to the e-paper display")
    p.add_argument("-f", "--file", default=None, help="BMP file path")
    p.add_argument("-r", "--rotate", default="CCW", choices=["CW", "CCW", "flip"])
    p.add_argument("-c", "--clear", action="store_true", help="Clear the display")
    args = p.parse_args()

    if args.clear:
        clear(rotate=args.rotate)
    elif args.file:
        send(args.file, rotate=args.rotate)
    else:
        print("Error: provide --file or --clear")
