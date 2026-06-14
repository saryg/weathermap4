import io
import logging
import math
import os
import pickle
import tempfile
import zipfile
from datetime import datetime, timedelta, timezone

import numpy as np
import requests
from PIL import Image

import config

logger = logging.getLogger(__name__)

_TIMEOUT = 15  # seconds


# ---------------------------------------------------------------------------
# Base map (shared by both radar sources)
# ---------------------------------------------------------------------------

def createBaseMap(country):
    import cartopy.crs as ccrs
    import cartopy.io.img_tiles as cimgt
    import matplotlib.pyplot as plt
    import shapefile
    from shapely.geometry import shape

    focus_countries, non_focus_countries = countryMapShape(country)

    proj = ccrs.Mercator(central_longitude=config.map_settings[country]["centre_lon"])
    fig, ax = plt.subplots(
        figsize=(config.screen_width / config.dpi, config.screen_height / config.dpi),
        dpi=config.dpi,
        subplot_kw={"projection": proj},
    )
    ax.set_extent(config.map_settings[country]["extent"])

    ax.add_geometries(
        non_focus_countries, ccrs.PlateCarree(),
        edgecolor="grey", facecolor="none", linewidth=0.6, zorder=2,
    )

    from shapely.ops import unary_union
    merged_focus = unary_union([g.buffer(0.001) for g in focus_countries]).buffer(-0.001)
    ax.add_geometries(
        [merged_focus], ccrs.PlateCarree(),
        edgecolor="black", facecolor="none", linewidth=1.4, zorder=2,
    )

    for place, coords in config.map_settings[country]["points_of_interest"].items():
        ax.plot(
            [coords[1]], [coords[0]],
            markeredgecolor="black", markerfacecolor="darkgray",
            marker="o", markersize=7, fillstyle="full",
            transform=ccrs.PlateCarree(),
        )

    plt.gca().set_position([0, 0, 1, 1])

    pickle_fn = config.pickle_path.format(country=country)
    os.makedirs(os.path.dirname(pickle_fn), exist_ok=True)
    os.makedirs(os.path.dirname(config.base_map_path.format(country=country)), exist_ok=True)
    with open(pickle_fn, "wb") as f:
        pickle.dump(ax, f)
    logger.info("Saved base map pickle for %s", country)
    plt.savefig(config.base_map_path.format(country=country))
    return ax


def loadOrCreateBaseMapPickle(country):
    pickle_fn = config.pickle_path.format(country=country)
    try:
        with open(pickle_fn, "rb") as f:
            ax = pickle.load(f)
        logger.info("Loaded base map pickle for %s", country)
        return ax
    except FileNotFoundError:
        logger.info("Base map pickle not found — creating for %s", country)
    except Exception as e:
        logger.warning("Could not load base map pickle (%s) — recreating", e)
    return createBaseMap(country)


def countryMapShape(country):
    import shapefile
    from shapely.geometry import shape

    try:
        sf = shapefile.Reader(config.map_unit_shapefile_path)
    except Exception as e:
        raise RuntimeError(f"Could not read shapefile at {config.map_unit_shapefile_path}: {e}")

    shapes = sf.shapes()
    records = sf.records()

    # Field indices for ne_10m_admin_0_map_units shapefile:
    #   records[i][16] = GU_A3 (3-letter unit code, e.g. "IRL", "NIR", "ENG")
    #   records[i][10] = ADM0_A3 (sovereign country code, fallback for territories)
    focus_countries = []
    for code in config.map_settings[country]["focus_country_codes"]:
        for idx in [i for i in range(len(records)) if records[i][16] == code]:
            focus_countries.append(shape(shapes[idx]))

    non_focus_countries = []
    for code in config.map_settings[country]["non_focus_country_codes"]:
        idxs = [i for i in range(len(records)) if records[i][16] == code]
        if not idxs:
            idxs = [i for i in range(len(records)) if records[i][10] == code]
        for idx in idxs:
            non_focus_countries.append(shape(shapes[idx]))

    return focus_countries, non_focus_countries


# ---------------------------------------------------------------------------
# RainViewer source
# ---------------------------------------------------------------------------

def getLatestRadarPath():
    """Return the path for the most recent RainViewer radar frame, e.g. '/v2/radar/abc123'."""
    try:
        response = requests.get(config.rainviewer_timestamp_url, timeout=_TIMEOUT)
        response.raise_for_status()
        return response.json()["radar"]["past"][-1]["path"]
    except requests.exceptions.Timeout:
        raise RuntimeError(f"RainViewer timestamp request timed out after {_TIMEOUT}s")
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(f"Could not connect to RainViewer: {e}")
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"RainViewer returned an error: {e}")
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected RainViewer response format: {e}")
    except Exception as e:
        raise RuntimeError(f"Unexpected error fetching radar path: {e}")


def makeRadarMap(country, path=None):
    """Render radar via RainViewer tile CDN onto the cartopy base map."""
    import cartopy.crs as ccrs
    import cartopy.io.img_tiles as cimgt
    import matplotlib.pyplot as plt

    if path is None:
        path = getLatestRadarPath()

    # Render radar tiles onto a blank figure — no outlines, no base map
    proj = ccrs.Mercator(central_longitude=config.map_settings[country]["centre_lon"])
    fig, ax = plt.subplots(
        figsize=(config.screen_width / config.dpi, config.screen_height / config.dpi),
        dpi=config.dpi,
        subplot_kw={"projection": proj},
    )
    ax.set_extent(config.map_settings[country]["extent"])
    ax.set_facecolor("white")

    z = config.map_settings[country]["zoom"]
    url = config.rainviewer_radar_tile_url.format(
        path=path, x="{x}", y="{y}", z="{z}"
    )
    tiles = cimgt.GoogleTiles(url=url, desired_tile_form="RGBA")
    ax.add_image(tiles, z)
    ax.set_position([0, 0, 1, 1])

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name
    plt.savefig(tmp_path)
    plt.close(fig)

    _remap_rainviewer_to_grayscale(tmp_path, country)
    os.unlink(tmp_path)
    logger.info("Saved radar map")
    return config.radar_map_path


# ---------------------------------------------------------------------------
# Met Éireann polar radar source
# ---------------------------------------------------------------------------

def getLatestMetRadarFiles():
    """Return the most recent Dublin and Shannon PAGZ HDF5 file records from Met Éireann."""
    now = datetime.now(timezone.utc)
    try:
        response = requests.get(
            config.met_radar_listing_url,
            params={
                "from": (now - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%S"),
                "to": now.strftime("%Y-%m-%dT%H:%M:%S"),
            },
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        files = response.json()
    except requests.exceptions.Timeout:
        raise RuntimeError(f"Met Éireann radar listing timed out after {_TIMEOUT}s")
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(f"Could not connect to Met Éireann API: {e}")
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"Met Éireann API returned an error: {e}")
    except Exception as e:
        raise RuntimeError(f"Unexpected error fetching Met Éireann radar files: {e}")

    dublin = sorted([f for f in files if "PAGZ41" in f["name"]], key=lambda x: x["timestamp"])
    shannon = sorted([f for f in files if "PAGZ40" in f["name"]], key=lambda x: x["timestamp"])

    if not dublin and not shannon:
        raise RuntimeError("No recent Met Éireann radar files available")

    result = {}
    if dublin:
        result["dublin"] = dublin[-1]
    if shannon:
        result["shannon"] = shannon[-1]
    return result


def makeRadarMapMet(country, files=None):
    """Render radar from Met Éireann polar HDF5 files onto the base map. No cartopy needed."""
    if country != "Ireland":
        raise ValueError(f"Met Éireann radar only supports Ireland, not {country!r}")

    if files is None:
        files = getLatestMetRadarFiles()

    base_path = config.base_map_path.format(country=country)
    base = Image.open(base_path).convert("RGBA")
    overlay_arr = np.zeros((config.screen_height, config.map_display_width, 4), dtype=np.uint8)

    map_settings = config.map_settings[country]

    for label, file_record in files.items():
        filename = file_record["name"]
        logger.info("Fetching Met Éireann radar: %s", filename)

        try:
            response = requests.get(
                config.met_radar_download_url,
                params={"files": filename},
                timeout=_TIMEOUT,
            )
            response.raise_for_status()
        except Exception as e:
            logger.warning("Could not download %s: %s — skipping", filename, e)
            continue

        z = zipfile.ZipFile(io.BytesIO(response.content))
        tmp = tempfile.NamedTemporaryFile(suffix=".h5", delete=False)
        try:
            tmp.write(z.read(z.namelist()[0]))
            tmp.close()
            lats, lons, dbz = _read_polar_h5(tmp.name)
        finally:
            os.unlink(tmp.name)

        px, py = _latlon_to_pixel(lats, lons, map_settings)
        colours = _dbz_to_rgba(dbz)

        in_bounds = (px >= 0) & (px < config.map_display_width) & (py >= 0) & (py < config.screen_height)
        rain = in_bounds & (dbz >= 10)
        ry, rx, rc = py[rain], px[rain], colours[rain]
        # Dilate each bin to a 5×5 square to fill gaps between azimuth rays at range
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                oy = np.clip(ry + dy, 0, config.screen_height - 1)
                ox = np.clip(rx + dx, 0, config.map_display_width - 1)
                overlay_arr[oy, ox] = rc
        logger.info("Rendered %s radar: %d rain pixels", label, int(rain.sum()))

    from PIL import ImageFilter
    overlay = Image.fromarray(overlay_arr, "RGBA")
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=3))
    base.paste(overlay, (0, 0), overlay)
    base.convert("RGB").save(config.radar_map_path)
    logger.info("Saved Met Éireann radar map")
    return config.radar_map_path


def _read_polar_h5(path):
    """Read lowest-elevation DBZH scan from an ODIM HDF5 polar volume. Returns lats, lons, dbz arrays."""
    import h5py

    with h5py.File(path, "r") as hf:
        radar_lat = float(hf["where"].attrs["lat"])
        radar_lon = float(hf["where"].attrs["lon"])
        d = hf["dataset1"]  # lowest elevation scan
        nbins  = int(d["where"].attrs["nbins"])
        nrays  = int(d["where"].attrs["nrays"])
        rscale = float(d["where"].attrs["rscale"])
        rstart = float(d["where"].attrs["rstart"])
        raw    = d["data1/data"][:]
        gain   = float(d["data1/what"].attrs["gain"])
        offset = float(d["data1/what"].attrs["offset"])
        nodata = float(d["data1/what"].attrs["nodata"])
        undetect = float(d["data1/what"].attrs["undetect"])

    dbz = raw.astype(np.float32) * gain + offset
    dbz[raw == int(nodata)]    = np.nan
    dbz[raw == int(undetect)]  = np.nan

    # Vectorised polar → geographic conversion
    # Azimuth: 0° = North, clockwise. Range in metres.
    azimuths = np.radians(np.arange(nrays))[:, None]        # (nrays, 1)
    ranges   = (rstart + rscale * np.arange(nbins))[None, :] # (1, nbins)
    d_ang    = ranges / 6_371_000.0                           # angular distance on sphere

    lat0 = math.radians(radar_lat)
    lon0 = math.radians(radar_lon)

    lats = np.degrees(
        np.arcsin(np.sin(lat0) * np.cos(d_ang) + np.cos(lat0) * np.sin(d_ang) * np.cos(azimuths))
    )
    lons = np.degrees(
        lon0 + np.arctan2(
            np.sin(azimuths) * np.sin(d_ang) * np.cos(lat0),
            np.cos(d_ang) - np.sin(lat0) * np.sin(np.radians(lats)),
        )
    )
    return lats, lons, dbz


def _latlon_to_pixel(lats, lons, map_settings):
    """Convert lat/lon arrays to pixel coordinates using the map's Mercator projection."""
    ext = map_settings["extent"]  # [west, east, south, north]
    central_lon = map_settings["centre_lon"]
    west, east, south, north = ext

    x_min = math.radians(west  - central_lon)
    x_max = math.radians(east  - central_lon)
    y_min = math.log(math.tan(math.pi / 4 + math.radians(south) / 2))
    y_max = math.log(math.tan(math.pi / 4 + math.radians(north) / 2))

    x = np.radians(lons - central_lon)
    y = np.log(np.tan(np.pi / 4 + np.radians(lats) / 2))

    px = ((x - x_min) / (x_max - x_min) * config.map_display_width).astype(int)
    py = ((y_max - y) / (y_max - y_min) * config.screen_height).astype(int)
    return px, py


def _remap_rainviewer_to_grayscale(radar_tiles_path, country):
    """
    Remap RainViewer tile colors to e-paper grayscale using the official Universal Blue
    (scheme 2) color table from rainviewer.com/api/color-schemes.html.
    Each pixel is matched to the nearest dBZ entry by Euclidean RGB distance,
    then mapped linearly to a 16-level grayscale (darker = heavier rain).
    """
    from PIL import ImageFilter

    # Official Universal Blue (scheme 2) RGB table: [dBZ, R, G, B]
    # Source: rainviewer.com/api/color-schemes.html, column index 2 of the embedded JSON table
    _SCHEME2 = np.array([
        [10, 0xdf, 0xdf, 0xdf], [11, 0xd1, 0xe1, 0xcf], [12, 0xc3, 0xe3, 0xbf],
        [13, 0xb6, 0xe5, 0xaf], [14, 0xa8, 0xe7, 0x9f], [15, 0x9b, 0xea, 0x8f],
        [16, 0x8d, 0xee, 0x7f], [17, 0x80, 0xf2, 0x70], [18, 0x72, 0xf6, 0x60],
        [19, 0x65, 0xfa, 0x51], [20, 0x58, 0xff, 0x42], [21, 0x54, 0xf2, 0x4c],
        [22, 0x51, 0xe6, 0x57], [23, 0x4d, 0xda, 0x62], [24, 0x4a, 0xce, 0x6d],
        [25, 0x47, 0xc2, 0x78], [26, 0x47, 0xb8, 0x91], [27, 0x47, 0xaf, 0xab],
        [28, 0x47, 0xa5, 0xc5], [29, 0x47, 0x9c, 0xdf], [30, 0x47, 0x93, 0xf9],
        [31, 0x3b, 0x87, 0xfa], [32, 0x2f, 0x7b, 0xfb], [33, 0x23, 0x70, 0xfc],
        [34, 0x17, 0x64, 0xfd], [35, 0x0c, 0x59, 0xff], [36, 0x1d, 0x57, 0xf2],
        [37, 0x2e, 0x56, 0xe6], [38, 0x3f, 0x55, 0xd9], [39, 0x50, 0x54, 0xcd],
        [40, 0x61, 0x53, 0xc1], [41, 0x80, 0x5f, 0xbb], [42, 0xa0, 0x6c, 0xb5],
        [43, 0xbf, 0x79, 0xaf], [44, 0xdf, 0x86, 0xa9], [45, 0xff, 0x93, 0xa3],
        [46, 0xff, 0x82, 0x8d], [47, 0xff, 0x71, 0x77], [48, 0xff, 0x60, 0x61],
        [49, 0xff, 0x4f, 0x4b], [50, 0xff, 0x3f, 0x35], [51, 0xf2, 0x33, 0x2d],
        [52, 0xe6, 0x27, 0x26], [53, 0xda, 0x1c, 0x1f], [54, 0xce, 0x10, 0x18],
        [55, 0xc2, 0x05, 0x11], [56, 0xce, 0x33, 0x0f], [57, 0xda, 0x61, 0x0e],
        [58, 0xe6, 0x8f, 0x0c], [59, 0xf2, 0xbd, 0x0b], [60, 0xff, 0xeb, 0x0a],
        [61, 0xff, 0xda, 0x0b], [62, 0xff, 0xc9, 0x0c], [63, 0xff, 0xb9, 0x0e],
        [64, 0xff, 0xa8, 0x0f], [65, 0xff, 0x98, 0x11],
    ], dtype=np.float32)

    dbz_vals  = _SCHEME2[:, 0]   # (N,)
    table_rgb = _SCHEME2[:, 1:]  # (N, 3)

    # dBZ 10 → gray 208 (e-paper level 13), dBZ 65 → gray 16 (level 1)
    table_gray = np.clip(208.0 - (dbz_vals - 10.0) / 55.0 * 192.0, 16.0, 208.0).astype(np.uint8)

    img = Image.open(radar_tiles_path).convert("RGB")
    arr = np.array(img, dtype=np.float32)

    # Any pixel that differs from the white tile background is radar
    is_radar = np.max(255.0 - arr, axis=2) > 15

    # Nearest-neighbour match in RGB space → dBZ → grayscale
    pixels = arr[is_radar]  # (M, 3)
    dists = np.sum((pixels[:, np.newaxis, :] - table_rgb[np.newaxis, :, :]) ** 2, axis=2)
    gray = table_gray[np.argmin(dists, axis=1)]  # (M,)

    # Isolate radar layer, blur, composite onto desaturated base
    radar_layer = np.zeros((arr.shape[0], arr.shape[1], 4), dtype=np.uint8)
    radar_layer[is_radar, 0] = gray
    radar_layer[is_radar, 1] = gray
    radar_layer[is_radar, 2] = gray
    radar_layer[is_radar, 3] = 220

    radar_img = Image.fromarray(radar_layer, "RGBA").filter(ImageFilter.GaussianBlur(radius=3))
    base_map_path = config.base_map_path.format(country=country)
    if not os.path.exists(base_map_path):
        logger.info("Base map PNG missing — regenerating for %s", country)
        createBaseMap(country)
    base = Image.open(base_map_path).convert("RGB")
    base.paste(radar_img, (0, 0), radar_img)
    base.save(config.radar_map_path)


def _dbz_to_rgba(dbz):
    """Map dBZ to grayscale RGBA optimised for 16-level e-paper. Darker = heavier rain."""
    rgba = np.zeros((*dbz.shape, 4), dtype=np.uint8)
    # Gray values snapped to nearest of 16 e-paper levels (0, 16, 32, ... 240, 255)
    # Light rain is pale; heavy rain approaches black.
    levels = [
        (10, 20,  (208, 208, 208, 160)),  # level 13 — very light
        (20, 30,  (176, 176, 176, 180)),  # level 11 — light
        (30, 40,  (128, 128, 128, 200)),  # level  8 — medium
        (40, 50,  ( 80,  80,  80, 220)),  # level  5 — dark
        (50, 60,  ( 48,  48,  48, 235)),  # level  3 — very dark
        (60, 999, ( 16,  16,  16, 250)),  # level  1 — near black
    ]
    for lo, hi, col in levels:
        rgba[(dbz >= lo) & (dbz < hi)] = col
    return rgba


if __name__ == "__main__":
    createBaseMap("Ireland")
    makeRadarMap("Ireland")
