import datetime
import logging
from concurrent.futures import ThreadPoolExecutor

from dateutil import parser as prs
from PIL import Image, ImageOps, ImageDraw

import config
from weathermap import forecast

logger = logging.getLogger(__name__)


def build(args):
    """Build the weathermap image and save it. Returns the output file path."""
    config.load_fonts()

    location = args.weather_location
    country = args.map_country
    show_warnings = args.warnings
    current_conditions = args.current_conditions
    weather_forecast = args.forecast
    subtle = args.subtle
    sidebar = args.sidebar
    show_radar = args.radar

    # Fetch radar path and forecast concurrently to overlap network wait
    radar_path = None
    forecast_data = None

    if show_radar:
        from weathermap import radar
        radar_source = config.RADAR_SOURCE

    with ThreadPoolExecutor(max_workers=2) as executor:
        if show_radar:
            if radar_source == "met":
                future_radar = executor.submit(radar.getLatestMetRadarFiles)
            else:
                future_radar = executor.submit(radar.getLatestRadarPath)
        else:
            future_radar = None
        future_forecast = (
            executor.submit(forecast.getForecast, config.forecast_locations[location]["coords"])
            if weather_forecast else None
        )
        if future_radar is not None:
            try:
                radar_data = future_radar.result()
            except Exception:
                logger.exception("Radar fetch failed")
                radar_data = None
        if future_forecast is not None:
            try:
                forecast_data = future_forecast.result()
            except Exception:
                logger.exception("Forecast fetch failed")

    if show_radar:
        try:
            if radar_source == "met":
                radar_img_fn = radar.makeRadarMapMet(country, files=radar_data)
            else:
                radar_img_fn = radar.makeRadarMap(country, path=radar_data)
            image = Image.open(radar_img_fn)
            logger.info("Radar map loaded")
        except Exception:
            logger.exception("Radar map failed — falling back to base map")
            base_path = config.base_map_path.format(country=country)
            try:
                image = Image.open(base_path)
            except Exception:
                logger.exception("Base map also unavailable at %s", base_path)
                raise
            image = addRadarErrorMessage(image)
    else:
        base_path = config.base_map_path.format(country=country)
        try:
            image = Image.open(base_path)
        except FileNotFoundError:
            logger.info("Base map not found — generating for %s", country)
            from weathermap import radar
            radar.createBaseMap(country)
            image = Image.open(base_path)

    if country == "Ireland" and show_warnings:
        try:
            weather_warnings = forecast.getWeatherWarnings(
                config.forecast_locations[location]["region"]
            )
            if weather_warnings:
                image = addWeatherWarnings(image, weather_warnings)
        except Exception:
            logger.exception("Weather warnings unavailable — continuing without them")

    if weather_forecast:
        if forecast_data is None:
            image = addEmptySidebar(image)
            image = addErrorMessage(image)
        else:
            if sidebar:
                try:
                    image = addSidebar(image, forecast_data)
                except Exception:
                    logger.exception("Sidebar rendering failed — showing empty sidebar")
                    image = addEmptySidebar(image)
            else:
                image = addEmptySidebar(image)

            try:
                if subtle:
                    image = addSubtleWeatherDescriptions(image, forecast_data, forecast_location=location)
                else:
                    image = addWeatherDescriptions(image, forecast_data, forecast_location=location)
            except Exception:
                logger.exception("Weather descriptions rendering failed — skipping")

            if current_conditions:
                try:
                    font_colour = "white" if subtle else "black"
                    image = addCurrentConditions(image, forecast_data, font_colour)
                except Exception:
                    logger.exception("Current conditions rendering failed — skipping")
    else:
        image = addEmptySidebar(image)

    image.save(config.weathermap_bmp_path, "BMP")
    logger.info("Saved to %s", config.weathermap_bmp_path)
    return config.weathermap_bmp_path


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------

def _wrap_text(draw, font, text, max_width_px, max_lines=3):
    """Word-wrap text to fit max_width_px. Truncates with '…' if it exceeds max_lines."""
    words = text.split()
    if not words:
        return [""]

    def text_w(s):
        bbox = draw.textbbox((0, 0), s, font=font)
        return bbox[2] - bbox[0]

    lines, cur = [], ""
    for idx, word in enumerate(words):
        test = (cur + " " + word).strip()
        if text_w(test) <= max_width_px:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = word
            if len(lines) == max_lines - 1:
                remaining = " ".join([cur] + words[idx + 1:])
                ell = "…"
                while remaining and text_w(remaining + ell) > max_width_px:
                    remaining = remaining[:-1]
                lines.append((remaining.rstrip() + ell) if remaining else ell)
                return lines
    if cur:
        lines.append(cur)
    return lines[:max_lines]

def addSidebar(image, forecast_data):
    """Draw the right-hand forecast sidebar: hourly icon, temp, rain chance, UV for the next ~12 hours."""
    sb_x = config.map_display_width
    sidebar = Image.new("RGBA", (config.sidebar_width, config.sidebar_height), "black")
    image.paste(sidebar, (sb_x, 0))

    draw = ImageDraw.Draw(image)
    current_hour = datetime.datetime.fromisoformat(forecast_data["current_weather"]["time"]).hour

    # Reserve space at top (clears the top bar) and bottom (timestamp)
    top_reserve = 80
    bottom_reserve = 30
    hourly_len = len(forecast_data["hourly"]["weathercode"])
    # Start ~2 h from now, show up to 4 slots at 3 h intervals (~12 h ahead)
    hours = [h for h in range(current_hour + 2, current_hour + 15, 3) if h < hourly_len]
    n_slots = len(hours)
    if n_slots == 0:
        return image

    # Divide available height evenly so slots never overlap or drift
    slot_height = (config.screen_height - top_reserve - bottom_reserve) // n_slots

    for slot_idx, hour in enumerate(hours):
        slot_top = top_reserve + slot_idx * slot_height
        line_padding = 4

        day_night_icon = isDayNight(hour, forecast_data)
        hour_24 = hour % 24
        hour_12 = 12 if hour_24 in [0, 12] else hour % 12
        am_pm_str = amPmDayNight(hour_24)
        weathercode = forecast_data["hourly"]["weathercode"][hour]

        y = slot_top + 8
        text = str(hour_12) + " " + am_pm_str
        font = config.MED_FONT
        new_x, _, text_height = centreTextHorizontally(draw, text, font, sb_x, config.screen_width)
        draw.text((new_x, y), text, fill="white", font=font)
        y += text_height + line_padding

        icon_size = config.MED_ICON_SIZE
        forecast_icon_path = config.icon_path + forecast.weather_codes[weathercode][day_night_icon]
        _, forecast_icon = setup_icon_image(forecast_icon_path, icon_size)
        new_x = centreIconHorizontally(icon_size[0], sb_x, config.screen_width)
        image.paste(forecast_icon, (new_x, y), forecast_icon)
        y += icon_size[1] - 10

        text = " " + str(round(forecast_data["hourly"]["temperature_2m"][hour])) + "°"
        new_x, _, text_height = centreTextHorizontally(draw, text, config.LARGE_FONT, sb_x, config.screen_width)
        draw.text((new_x, y), text, fill="white", font=config.LARGE_FONT)
        y += text_height + line_padding

        precip = round(forecast_data["hourly"]["precipitation_probability"][hour])
        if precip > 0:
            rain_text = str(precip) + "%"
            small_icon = config.SMALLER_ICON_SIZE
            _, text_width, _ = centreTextHorizontally(draw, rain_text, config.SMALL_FONT, sb_x, config.screen_width)
            edge_padding_x = (config.sidebar_width - small_icon[1] - text_width) / 2
            icon_start_x = round(sb_x + edge_padding_x)
            _, umbrella_icon = setup_icon_image(config.icon_path + "umbrella.png", small_icon)
            image.paste(umbrella_icon, (icon_start_x, y), umbrella_icon)
            draw.text((round(icon_start_x + small_icon[0]), y), rain_text, fill="white", font=config.SMALL_FONT)
            y += small_icon[1]

        uv = round(forecast_data["hourly"]["uv_index"][hour])
        if uv > 0:
            uv_text = "UV " + str(uv)
            new_x, _, _ = centreTextHorizontally(draw, uv_text, config.SMALL_FONT, sb_x, config.screen_width)
            draw.text((new_x, y), uv_text, fill="white", font=config.SMALL_FONT)

    current_time = datetime.datetime.now().strftime("%H:%M")
    new_x, _, text_height = centreTextHorizontally(draw, current_time, config.SMALLER_FONT, sb_x, config.screen_width)
    y_pos = config.screen_height - line_padding - text_height
    draw.text((new_x, y_pos), current_time, fill="white", font=config.SMALLER_FONT)

    return image


def addEmptySidebar(image):
    sb_x = config.map_display_width
    sidebar = Image.new("RGBA", (config.sidebar_width, config.sidebar_height), "black")
    image.paste(sidebar, (sb_x, 0))
    return image


def isDayNight(hour, forecast_data):
    return "day_icon" if forecast_data["hourly"]["is_day"][hour] == 1 else "night_icon"


def addSubtleWeatherDescriptions(image, forecast_data, forecast_location):
    """Overlay current conditions on the map with black bars top and bottom (subtle/dark mode)."""
    top_bar_h = 60
    line_padding = 4

    quarter_icon_size = (155, 155)
    quarter_icon_path = config.icon_path + "quarter.jpg"
    quarter_icon, _ = setup_icon_image(quarter_icon_path, quarter_icon_size)
    image.paste(quarter_icon, (0, 0), quarter_icon)

    quarter_icon_size = (150, 155)
    quarter_icon, _ = setup_icon_image(quarter_icon_path, quarter_icon_size)
    quarter_icon = quarter_icon.convert("RGBA")
    quarter_icon = quarter_icon.rotate(270, resample=Image.BICUBIC, expand=False)
    image.paste(quarter_icon, (config.map_display_width - quarter_icon_size[1] + 5, 0), quarter_icon)

    bar = Image.new("RGBA", (config.map_display_width, top_bar_h), "black")
    image.paste(bar, (0, 0))
    image.paste(bar, (0, config.screen_height - top_bar_h))

    draw = ImageDraw.Draw(image)

    # Vertically centre content in the top bar, nudged down slightly
    top_bar_text_y = (top_bar_h - config.SMALL_ICON_SIZE[1]) // 2 + 5
    icon_size = config.SMALL_ICON_SIZE
    font_size = config.SMALL_FONT

    sunrise_dt = datetime.datetime.fromisoformat(forecast_data["daily"]["sunrise"][0])
    placeIconAndData(draw, image, top_bar_text_y, 160, config.map_display_width / 2,
                     config.icon_path + "sunrise.png", sunrise_dt.strftime("%H:%M"),
                     icon_size, font_size, "white")

    sunset_dt = datetime.datetime.fromisoformat(forecast_data["daily"]["sunset"][0])
    placeIconAndData(draw, image, top_bar_text_y, round(config.map_display_width / 2), config.map_display_width - 160,
                     config.icon_path + "sunset.png", sunset_dt.strftime("%H:%M"),
                     icon_size, font_size, "white")

    day_night_icon = "day_icon" if forecast_data["current_weather"]["is_day"] == 1 else "night_icon"
    main_weather_icon_path = (
        config.icon_path + forecast.weather_codes[forecast_data["current_weather"]["weathercode"]][day_night_icon]
    )
    icon_size = config.LARGE_ICON_SIZE
    font_size = config.LARGE_FONT
    _, main_icon_white = setup_icon_image(main_weather_icon_path, icon_size)

    current_dt = datetime.datetime.fromisoformat(forecast_data["current_weather"]["time"])
    text_str = f"{forecast_location},  {current_dt.strftime('%d/%m')}"
    temp_str = str(round(forecast_data["current_weather"]["temperature"])) + "°"

    start_x = 0
    end_x = config.map_display_width

    # Centre icon and temp vertically within the 155px quarter-circle, nudged up slightly
    quarter_h = 155
    icon_y = (quarter_h - icon_size[1]) // 2 - 5
    image.paste(main_icon_white, (config.map_display_width - icon_size[1] - 15, icon_y), main_icon_white)

    draw.text((30, icon_y), temp_str, fill="white", font=config.EXTRA_LARGE_FONT)

    # Location and description just below the quarter-circle decorations
    current_y = quarter_h + 20
    _, text_w, text_h = centreTextHorizontally(draw, text_str, font_size, start_x, end_x)
    text_start_x = round(start_x + (end_x - text_w) / 2)
    draw.text((text_start_x, current_y), text_str, fill="black", font=font_size, stroke_width=2, stroke_fill="white")
    current_y += text_h + line_padding * 2

    desc_str = forecast.weather_codes[forecast_data["current_weather"]["weathercode"]]["desc"]
    centered_x, _, _ = centreTextHorizontally(draw, desc_str, font_size, start_x, end_x)
    draw.text((centered_x, current_y), desc_str, fill="black", font=font_size, stroke_width=2, stroke_fill="white")
    return image


def addWeatherDescriptions(image, forecast_data, forecast_location):
    current_y = 140
    line_padding = 4
    draw = ImageDraw.Draw(image)

    current_dt = datetime.datetime.fromisoformat(forecast_data["current_weather"]["time"])
    text_str = f"{forecast_location}, {current_dt.strftime('%d/%m')}"

    day_night_icon = "day_icon" if forecast_data["current_weather"]["is_day"] == 1 else "night_icon"
    main_weather_icon_path = (
        config.icon_path + forecast.weather_codes[forecast_data["current_weather"]["weathercode"]][day_night_icon]
    )
    icon_size = config.LARGE_ICON_SIZE
    font_size = config.LARGE_FONT
    main_icon, _ = setup_icon_image(main_weather_icon_path, icon_size)

    start_x = 0
    end_x = config.map_display_width
    _, text_w, text_h = centreTextHorizontally(draw, text_str, font_size, start_x, end_x)
    edge_padding_x = (end_x - icon_size[1] - text_w) / 2
    icon_start_x = round(start_x + edge_padding_x)
    text_start_x = round(icon_start_x + icon_size[0])

    image.paste(main_icon, (icon_start_x, current_y - 15), main_icon)
    draw.text((text_start_x, current_y), text_str, fill="black", font=font_size)
    current_y += text_h + line_padding

    text_str = forecast.weather_codes[forecast_data["current_weather"]["weathercode"]]["desc"]
    font_size = config.MED_FONT
    centered_text_x, _, text_h = centreTextHorizontally(draw, text_str, font_size, start_x, end_x)
    draw.text((centered_text_x, current_y), text_str, fill="black", font=font_size)
    current_y += text_h + line_padding

    text_str = str(round(forecast_data["current_weather"]["temperature"])) + "°"
    font_size = config.LARGE_FONT
    new_x, _, _ = centreTextHorizontally(draw, text_str, font_size, 0, end_x)
    draw.text((new_x, current_y), text_str, fill="black", font=font_size)
    current_y += 10

    # Split sunrise/sunset evenly across the map width
    sunrise_dt = datetime.datetime.fromisoformat(forecast_data["daily"]["sunrise"][0])
    sunset_dt = datetime.datetime.fromisoformat(forecast_data["daily"]["sunset"][0])
    icon_size = config.SMALL_ICON_SIZE
    font_size = config.SMALL_FONT
    mid_x = round(config.map_display_width / 2)
    placeIconAndData(draw, image, current_y, 0, mid_x, config.icon_path + "sunrise.png",
                     sunrise_dt.strftime("%H:%M"), icon_size, font_size, "white")
    placeIconAndData(draw, image, current_y, mid_x, config.map_display_width, config.icon_path + "sunset.png",
                     sunset_dt.strftime("%H:%M"), icon_size, font_size, "black")

    return image


def centreTextHorizontally(draw, text, font, x_start, x_end):
    text_length = draw.textlength(text, font=font)
    section_width = x_end - x_start
    centered_text_x = round((section_width / 2) - (text_length / 2) + x_start)
    _, _, w, h = draw.textbbox((0, 0), text, font=font)
    return centered_text_x, w, h


def centreIconHorizontally(icon_width, x_start, x_end):
    return round((x_end - x_start) / 2 - icon_width / 2 + x_start)


def addErrorMessage(image):
    draw = ImageDraw.Draw(image)
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    draw.text((80, config.screen_height - 110), f"{current_time} Error retrieving forecast!",
              fill="black", font=config.SMALLER_FONT, stroke_width=2, stroke_fill="white")
    return image


def addRadarErrorMessage(image):
    draw = ImageDraw.Draw(image)
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    draw.text((80, config.screen_height - 90), f"{current_time} Error retrieving radar images!",
              fill="black", font=config.SMALLER_FONT, stroke_width=2, stroke_fill="white")
    return image


def addWeatherWarnings(image, weather_warning_data):
    """Overlay active Met Éireann warnings on the map. Skips advisories and blight warnings. Shows up to 3."""
    draw = ImageDraw.Draw(image)

    warnings_to_draw = [
        w for w in weather_warning_data
        if w.get("type") != "Advisory"
        and "blight" not in w.get("headline", "").lower()
    ][:3]

    if not warnings_to_draw:
        return image

    icon_path = config.icon_path + "warning.png"
    font = config.SMALL_FONT
    icon_size = config.MED_ICON_SIZE
    font_colour = "black"
    gap_icon_text = 10
    line_spacing = 6
    after_time_gap = 12
    time_gap_px = 2
    stroke_width = 2
    start_x = 0
    end_x = config.map_display_width
    top_bound = 875
    bottom_bound = 1175

    def text_w_h(text):
        bbox = draw.textbbox((0, 0), text, font=font)
        return (bbox[2] - bbox[0], bbox[3] - bbox[1])

    max_text_width_px = max(60, (end_x - start_x) - 40 - icon_size[0] - gap_icon_text)
    _, line_h = text_w_h("Ag")

    cached = []
    total_h = 0
    for w in warnings_to_draw:
        lines = _wrap_text(draw, font, f"{w.get('level', '')} {w.get('headline', '')}".strip(), max_text_width_px)
        cached.append(lines)
        headline_text_h = (len(lines) * line_h) + ((len(lines) - 1) * line_spacing)
        icon_y_offset = (line_h + (line_spacing // 2)) if len(lines) > 1 else 0
        block_h = max(5 + headline_text_h, icon_y_offset + icon_size[1])
        total_h += block_h + time_gap_px + line_h + after_time_gap

    start_fit_y = int(bottom_bound - total_h)
    if len(warnings_to_draw) == 1:
        current_y = max(top_bound, min(980, int(bottom_bound - total_h)))
    else:
        current_y = max(top_bound, start_fit_y)

    for w, headline_lines in zip(warnings_to_draw, cached):
        onset = prs.parse(w["onset"])
        expiry = prs.parse(w["expiry"])
        timing = f"{onset:%H:%M} {onset:%d/%m} - {expiry:%H:%M} {expiry:%d/%m}"

        widths = [text_w_h(ln)[0] for ln in headline_lines]
        text_block_w = max(widths) if widths else 0
        block_w = icon_size[0] + gap_icon_text + text_block_w
        icon_start_x = start_x + int(((end_x - start_x) - block_w) / 2)
        text_start_x = icon_start_x + icon_size[0] + gap_icon_text

        icon_y_offset = (line_h + (line_spacing // 2)) if len(headline_lines) > 1 else 0
        icon_y = current_y + icon_y_offset

        icon_black, icon_white = setup_icon_image(icon_path, icon_size)
        icon = icon_black if font_colour == "black" else icon_white
        image.paste(icon, (icon_start_x, icon_y), icon)

        text_y = current_y + 7
        for i, line in enumerate(headline_lines):
            draw.text((text_start_x, text_y + i * (line_h + line_spacing)), line,
                      fill=font_colour, font=font, stroke_width=stroke_width, stroke_fill="white")

        last_line_y = text_y + (len(headline_lines) - 1) * (line_h + line_spacing)
        headline_bottom = last_line_y + line_h
        icon_bottom = icon_y + icon_size[1]

        time_y = headline_bottom + time_gap_px
        draw.text((text_start_x, time_y), timing, fill="black", font=font, stroke_width=2, stroke_fill="white")

        _, timing_h = text_w_h(timing)
        current_y = max(time_y + timing_h, icon_bottom) + after_time_gap

    return image


def addCurrentConditions(image, forecast_data, font_colour):
    """Draw a row of current condition icons (rain %, humidity, cloud cover, UV, wind) near the bottom of the map."""
    draw = ImageDraw.Draw(image)
    y = 1130 if font_colour == "black" else 1150
    line_padding = 4
    padding = 25
    icon_offset = 7
    wonky_screen_offset = 10

    font = config.MED_FONT
    icon_size = config.ALMOST_MED_ICON_SIZE

    current_hour = datetime.datetime.fromisoformat(forecast_data["current_weather"]["time"]).hour

    precip = round(forecast_data["hourly"]["precipitation_probability"][current_hour])
    uv = round(forecast_data["hourly"]["uv_index"][current_hour])
    humidity_str = str(forecast_data["hourly"]["relativehumidity_2m"][current_hour]) + forecast_data["hourly_units"]["relativehumidity_2m"]
    cloudy_str = str(forecast_data["hourly"]["cloudcover"][current_hour]) + forecast_data["hourly_units"]["cloudcover"]
    wind_str = str(round(forecast_data["current_weather"]["windspeed"])) + forecast_data["hourly_units"]["windspeed_10m"]
    wind_deg = forecast_data["current_weather"]["winddirection"]

    all_conditions = [
        {"condition_type": "precipitation_probability", "condition_icon": "umbrella.png",     "condition_string": str(precip) + "%",   "condition_str_len": 0},
        {"condition_type": "humidity",                  "condition_icon": "humidity.png",      "condition_string": humidity_str,         "condition_str_len": 0},
        {"condition_type": "cloud_cover",               "condition_icon": "cloudy.png",        "condition_string": cloudy_str,           "condition_str_len": 0},
        {"condition_type": "uv",                                                               "condition_string": "UV " + str(uv),     "condition_str_len": 0},
        {"condition_type": "wind",                      "condition_icon": "wind-deg-crop.png", "condition_string": wind_str,             "condition_str_len": 0, "wind_deg": wind_deg},
    ]
    # Drop items with no meaningful value (no rain, no UV at night)
    conditions = [c for c in all_conditions
                  if not (c["condition_type"] == "precipitation_probability" and precip == 0)
                  and not (c["condition_type"] == "uv" and uv == 0)]

    total_text_length = 0
    for c in conditions:
        _, _, w, h = draw.textbbox((0, 0), c["condition_string"], font=font)
        total_text_length += int(w)
        c["condition_str_len"] = w

    n = len(conditions) - 1
    total_text_length += icon_size[1] * n
    while total_text_length + padding * n > config.map_display_width:
        padding -= 2
    total_text_length += padding * n
    current_x = wonky_screen_offset + round((config.map_display_width - total_text_length) / 2)

    for c in conditions:
        if c["condition_type"] == "wind":
            icon_path = config.icon_path + c["condition_icon"]
            icon_size = config.ALMOST_SMALL_ICON_SIZE
            icon_black, icon_white = setup_icon_image(icon_path, icon_size)
            icon = icon_white if font_colour == "white" else icon_black
            icon = icon.convert("RGBA").rotate(c["wind_deg"], resample=Image.BICUBIC, expand=False)
            image.paste(icon, (current_x, y + 3), icon)
            current_x += icon_size[1] + line_padding
        elif c["condition_type"] != "uv":
            icon_path = config.icon_path + c["condition_icon"]
            icon_black, icon_white = setup_icon_image(icon_path, icon_size)
            icon = icon_white if font_colour == "white" else icon_black
            image.paste(icon, (current_x, y - icon_offset), icon)
            current_x += icon_size[1]

        if c["condition_type"] in ("uv", "humidity"):
            current_x += line_padding if c["condition_type"] == "uv" else -6

        draw.text((current_x, y), c["condition_string"], fill=font_colour, font=font)

        if c["condition_type"] == "uv":
            current_x += line_padding
        current_x += c["condition_str_len"] + padding

    return image


def placeIconAndData(draw, image, ypos, start_x, end_x, icon_path, text_str, icon_size, font_size, font_colour):
    icon_black, icon_white = setup_icon_image(icon_path, icon_size)
    icon = icon_black if font_colour == "black" else icon_white

    _, text_w, _ = centreTextHorizontally(draw, text_str, font_size, start_x, end_x)
    edge_padding_x = (end_x - start_x - icon_size[1] - text_w) / 2
    icon_start_x = round(start_x + edge_padding_x)
    text_start_x = round(icon_start_x + icon_size[0])

    image.paste(icon, (icon_start_x, ypos), icon)
    stroke_width = 2 if font_colour == "black" else 0
    draw.text((text_start_x, ypos + 5), text_str, fill=font_colour, font=font_size, stroke_width=stroke_width, stroke_fill="white")
    return icon_size[1], icon_start_x, text_start_x


def amPmDayNight(hour):
    return "pm" if hour > 11 else "am"


def setup_icon_image(icon_path, icon_size):
    icon = Image.open(icon_path).convert("RGBA").resize(icon_size)
    r, g, b, a = icon.split()
    inverted = ImageOps.invert(Image.merge("RGB", (r, g, b)))
    r2, g2, b2 = inverted.split()
    return icon, Image.merge("RGBA", (r2, g2, b2, a))
