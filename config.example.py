"""
Copy this file to config.py and fill in your own locations.
config.py is gitignored — this file is the committed template.
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- User settings ---
WEATHER_LOCATION = "MyCity"   # must match a key in forecast_locations
MAP_COUNTRY = "Ireland"       # "Ireland" or "Germany"
SHOW_RADAR = True
RADAR_SOURCE = "rainviewer"  # "rainviewer" or "met" (Met Éireann, Ireland only)
SHOW_FORECAST = True
SHOW_SIDEBAR = True
SHOW_CURRENT_CONDITIONS = True
SHOW_WARNINGS = True
SUBTLE = True

# --- Display (Raspberry Pi only) ---
VCOM = -2.15  # check the sticker on your e-paper panel

# --- Locations ---
# Define your forecast location here. coords: [latitude, longitude]
# It will be automatically pinned on the map.
forecast_locations = {
    "MyCity": {
        "coords": [53.32, -6.27],
        "country": "Ireland",   # "Ireland" or "Germany"
        "region": "Dublin",     # county for Met Éireann warnings (Ireland only)
    },
}

# --- Extra map pins ---
# Optional extra locations to pin on the map (e.g. nearby cities).
# These are display-only and do not affect the forecast.
# Format: "Label": [latitude, longitude]
extra_map_pins = {
    "Ireland": {
        # "Cork": [51.8985, -8.4756],
        # "Galway": [53.2707, -9.0568],
    },
    "Germany": {
        # "Munich": [48.1351, 11.5820],
        # "Hamburg": [53.5753, 10.0153],
    },
}

# --- Paths (leave as-is unless you move files) ---
font_path = os.path.join(BASE_DIR, "fonts", "BebasNeue-Regular.ttf")
icon_path = os.path.join(BASE_DIR, "icons-transparent") + os.sep
base_map_path = os.path.join(BASE_DIR, "images", "{country}_base_map.png")
weathermap_bmp_path = os.path.join(BASE_DIR, "images", "weathermap.bmp")
map_unit_shapefile_path = os.path.join(BASE_DIR, "ne_10m_map_units", "ne_10m_admin_0_map_units.shp")
radar_map_path = os.path.join(BASE_DIR, "images", "radar_map.png")
pickle_path = os.path.join(BASE_DIR, "plots", "{country}.axes.pickle")

# --- Screen ---
screen_width = 825
screen_height = 1200
dpi = 150
sidebar_width = 80
sidebar_height = screen_height
map_display_width = screen_width - sidebar_width

# --- Icon sizes ---
SMALLER_ICON_SIZE = (30, 30)
ALMOST_SMALL_ICON_SIZE = (35, 35)
SMALL_ICON_SIZE = (40, 40)
ALMOST_MED_ICON_SIZE = (55, 55)
MED_ICON_SIZE = (60, 60)
LARGE_ICON_SIZE = (80, 80)

# --- Font sizes ---
FONT_SIZE_SMALLER     = 20
FONT_SIZE_SMALL       = 25
FONT_SIZE_MED         = 35
FONT_SIZE_LARGE       = 45
FONT_SIZE_LARGER      = 50
FONT_SIZE_EXTRA_LARGE = 65

# --- Fonts (loaded at build time, not at import) ---
SMALLER_FONT     = None
SMALL_FONT       = None
MED_FONT         = None
LARGE_FONT       = None
LARGER_FONT      = None
EXTRA_LARGE_FONT = None


def load_fonts():
    global SMALLER_FONT, SMALL_FONT, MED_FONT, LARGE_FONT, LARGER_FONT, EXTRA_LARGE_FONT
    from PIL import ImageFont
    SMALLER_FONT     = ImageFont.truetype(font_path, FONT_SIZE_SMALLER)
    SMALL_FONT       = ImageFont.truetype(font_path, FONT_SIZE_SMALL)
    MED_FONT         = ImageFont.truetype(font_path, FONT_SIZE_MED)
    LARGE_FONT       = ImageFont.truetype(font_path, FONT_SIZE_LARGE)
    LARGER_FONT      = ImageFont.truetype(font_path, FONT_SIZE_LARGER)
    EXTRA_LARGE_FONT = ImageFont.truetype(font_path, FONT_SIZE_EXTRA_LARGE)


# --- URLs (no API key required) ---
met_eireann_weather_warnings_url = (
    "https://www.met.ie/Open_Data/json/warning_{weather_warning_region}.json"
)
open_meteo_url = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude={latitude}&longitude={longitude}"
    "&hourly=temperature_2m,relativehumidity_2m,dewpoint_2m,apparent_temperature,"
    "precipitation_probability,precipitation,rain,showers,snowfall,snow_depth,"
    "weathercode,cloudcover,evapotranspiration,windspeed_10m,winddirection_10m,"
    "windgusts_10m,uv_index,uv_index_clear_sky,is_day"
    "&daily=weathercode,temperature_2m_max,temperature_2m_min,apparent_temperature_max,"
    "apparent_temperature_min,sunrise,sunset,uv_index_max,uv_index_clear_sky_max,"
    "precipitation_sum,rain_sum,showers_sum,snowfall_sum,precipitation_hours,"
    "precipitation_probability_max,windspeed_10m_max,windgusts_10m_max,"
    "winddirection_10m_dominant,et0_fao_evapotranspiration"
    "&current_weather=true&forecast_days=3&timezone={timezone}"
)
rainviewer_timestamp_url = "https://api.rainviewer.com/public/weather-maps.json"
rainviewer_radar_tile_url = (
    "https://tilecache.rainviewer.com{path}/256/{z}/{x}/{y}/2/1_1.png"
)
met_radar_listing_url  = "https://api.opendata.met.ie/api/near-realtime/radar"
met_radar_download_url = "https://opendata.met.ie/data-portal/near-realtime/download/radar"

# --- Map settings ---
map_settings = {
    "Ireland": {
        "centre_lon": -8,
        "centre_lat": 53,
        "zoom": 5,
        "extent": [-12.8, -2.4, 49, 58],
        "focus_country_codes": ["IRL", "NIR"],
        "non_focus_country_codes": ["WLS", "ENG", "SCT", "IMN"],
        "points_of_interest": {
            **{name: loc["coords"] for name, loc in forecast_locations.items() if loc["country"] == "Ireland"},
            **extra_map_pins.get("Ireland", {}),
        },
        "forecast_location": WEATHER_LOCATION,
        "tiles": {
            8: {"xrange": range(119, 125), "yrange": range(79, 87)},
            7: {"xrange": range(59, 63), "yrange": range(39, 43)},
            6: {"xrange": range(29, 32), "yrange": range(19, 22)},
            5: {"xrange": range(14, 16), "yrange": range(9, 11)},
            4: {"xrange": range(7, 8), "yrange": range(4, 6)},
        },
    },
    "Germany": {
        "centre_lon": 10,
        "zoom": 5,
        "extent": [3.2, 19.4, 43.75, 58.45],
        "focus_country_codes": ["DEU"],
        "non_focus_country_codes": [
            "FRA", "HUN", "DNK", "AUT", "CZE", "POL", "CHE",
            "BEL", "LUX", "NLD", "ITA", "HRV", "BIH", "SWE", "SVK", "SVN",
        ],
        "points_of_interest": {
            **{name: loc["coords"] for name, loc in forecast_locations.items() if loc["country"] == "Germany"},
            **extra_map_pins.get("Germany", {}),
        },
        "forecast_location": WEATHER_LOCATION,
        "tiles": {
            6: {"xrange": range(32, 36), "yrange": range(19, 24)},
            5: {"xrange": range(16, 18), "yrange": range(9, 12)},
        },
    },
}
