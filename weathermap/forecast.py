import logging

import requests

import config

logger = logging.getLogger(__name__)

_TIMEOUT = 15  # seconds


def _fetch_json(url, service):
    """GET url and return parsed JSON, raising RuntimeError with the service name on failure."""
    try:
        r = requests.get(url, timeout=_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.Timeout:
        raise RuntimeError(f"{service} request timed out after {_TIMEOUT}s")
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(f"Could not connect to {service}: {e}")
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"{service} returned an error: {e}")
    except Exception as e:
        raise RuntimeError(f"Unexpected error fetching from {service}: {e}")


def getForecast(location_latlon, timezone="auto"):
    latitude, longitude = location_latlon
    url = config.open_meteo_url.format(latitude=latitude, longitude=longitude, timezone=timezone)
    data = _fetch_json(url, "Open-Meteo")
    if "current_weather" not in data:
        raise RuntimeError(f"Open-Meteo response missing expected fields: {list(data.keys())}")
    return data


def getWeatherWarnings(region):
    fips = weather_warning_regions_FIPS.get(region)
    if fips is None:
        raise ValueError(f"Unknown warning region: {region!r}")
    url = config.met_eireann_weather_warnings_url.format(weather_warning_region=fips)
    return _fetch_json(url, "Met Éireann")


# FIPS codes used by the Met Éireann warnings API to identify Irish counties
weather_warning_regions_FIPS = {
    "Carlow": "EI01", "Cavan": "EI02", "Clare": "EI03", "Cork": "EI04",
    "Donegal": "EI06", "Dublin": "EI07", "Galway": "EI10", "Kerry": "EI11",
    "Kildare": "EI12", "Kilkenny": "EI13", "Leitrim": "EI14", "Laois": "EI15",
    "Limerick": "EI16", "Longford": "EI18", "Louth": "EI19", "Mayo": "EI20",
    "Meath": "EI21", "Monaghan": "EI22", "Offaly": "EI23", "Roscommon": "EI24",
    "Sligo": "EI25", "Tipperary": "EI26", "Waterford": "EI27", "Westmeath": "EI29",
    "Wexford": "EI30", "Wicklow": "EI31",
}

# WMO weather interpretation codes (Open-Meteo uses this standard)
weather_codes = {
    0:  {"desc": "Clear sky",               "day_icon": "day-sunny.png",          "night_icon": "night-clear.png"},
    1:  {"desc": "Mainly clear",            "day_icon": "day-sunny.png",          "night_icon": "night-clear.png"},
    2:  {"desc": "Partly cloudy",           "day_icon": "day-cloudy.png",         "night_icon": "night-alt-cloudy.png"},
    3:  {"desc": "Overcast",                "day_icon": "cloudy.png",             "night_icon": "cloudy.png"},
    45: {"desc": "Fog",                     "day_icon": "fog.png",                "night_icon": "fog.png"},
    48: {"desc": "Depositing rime fog",     "day_icon": "fog.png",                "night_icon": "fog.png"},
    51: {"desc": "Light drizzle",           "day_icon": "day-showers.png",        "night_icon": "night-alt-showers.png"},
    53: {"desc": "Moderate drizzle",        "day_icon": "day-showers.png",        "night_icon": "night-alt-showers.png"},
    55: {"desc": "Dense drizzle",           "day_icon": "day-showers.png",        "night_icon": "night-alt-showers.png"},
    56: {"desc": "Light freezing drizzle",  "day_icon": "day-sleet.png",          "night_icon": "night-alt-sleet.png"},
    57: {"desc": "Dense freezing drizzle",  "day_icon": "day-sleet.png",          "night_icon": "night-alt-sleet.png"},
    61: {"desc": "Light rain",              "day_icon": "day-rain.png",           "night_icon": "night-alt-rain.png"},
    63: {"desc": "Moderate rain",           "day_icon": "rain.png",               "night_icon": "rain.png"},
    65: {"desc": "Heavy rain",              "day_icon": "rain.png",               "night_icon": "rain.png"},
    66: {"desc": "Light freezing rain",     "day_icon": "hail.png",               "night_icon": "hail.png"},
    67: {"desc": "Heavy freezing rain",     "day_icon": "hail.png",               "night_icon": "hail.png"},
    71: {"desc": "Light snow",              "day_icon": "day-snow.png",           "night_icon": "night-alt-snow.png"},
    73: {"desc": "Moderate snow",           "day_icon": "snow.png",               "night_icon": "snow.png"},
    75: {"desc": "Heavy snow",              "day_icon": "snow.png",               "night_icon": "snow.png"},
    77: {"desc": "Snow grains",             "day_icon": "snow.png",               "night_icon": "snow.png"},
    80: {"desc": "Light rain showers",      "day_icon": "day-showers.png",        "night_icon": "night-alt-showers.png"},
    81: {"desc": "Moderate rain showers",   "day_icon": "showers.png",            "night_icon": "showers.png"},
    82: {"desc": "Heavy rain showers",      "day_icon": "showers.png",            "night_icon": "showers.png"},
    85: {"desc": "Light snow showers",      "day_icon": "day-snow.png",           "night_icon": "night-alt-snow.png"},
    86: {"desc": "Heavy snow showers",      "day_icon": "snow.png",               "night_icon": "snow.png"},
    95: {"desc": "Thunderstorm",            "day_icon": "thunderstorm.png",       "night_icon": "thunderstorm.png"},
    96: {"desc": "Thunderstorm with light hail", "day_icon": "day-storm-showers.png", "night_icon": "night-alt-storm-showers.png"},
    99: {"desc": "Thunderstorm with heavy hail", "day_icon": "storm-showers.png",     "night_icon": "storm-showers.png"},
}
