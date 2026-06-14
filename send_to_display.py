"""
Send a BMP image to the Waveshare e-paper display via IT8951.
Runs only on Raspberry Pi — importing this module on other systems is safe;
the IT8951 dependency is loaded lazily at call time.
"""
import argparse


def _make_display(vcom, rotate):
    try:
        from IT8951.display import AutoEPDDisplay
    except ImportError:
        raise RuntimeError(
            "IT8951 not available. Are you running on a Raspberry Pi with IT8951 installed?\n"
            "Run with --no-display to skip sending to the screen."
        )
    return AutoEPDDisplay(vcom=vcom, rotate=rotate, mirror=False, spi_hz=24000000)


def send(image_path, vcom=-2.15, rotate="CCW"):
    from PIL import Image
    from IT8951 import constants
    display = _make_display(vcom, rotate)
    print("VCOM set to", display.epd.get_vcom())
    display.frame_buf.paste(0xFF, box=(0, 0, display.width, display.height))
    img = Image.open(image_path)
    img.thumbnail((display.width, display.height))
    paste_coords = [display.width - img.size[0], display.height - img.size[1]]
    display.frame_buf.paste(img, paste_coords)
    display.draw_full(constants.DisplayModes.GC16)
    print("Done.")


def clear(vcom=-2.15, rotate="CCW"):
    display = _make_display(vcom, rotate)
    display.clear()
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
