# Pi Setup — Waveshare 9.7" E-Paper

Tested on Raspberry Pi 3B+ running Raspberry Pi OS Bookworm 64-bit (kernel 6.12.25, aarch64).
Display: Waveshare 9.7" e-Paper HAT (IT8951 controller, 1200×825px).

---

## 1. Operating system

Install **Raspberry Pi OS Lite (64-bit, Bookworm)** via Raspberry Pi Imager. Lite is enough — no desktop needed.

Enable SSH in the imager settings before flashing so you can connect headlessly.

---

## 2. Enable SPI

The IT8951 controller communicates over SPI.

```bash
sudo raspi-config
```

Navigate to **Interface Options → SPI → Enable**, then reboot.

Or edit `/boot/firmware/config.txt` directly (Bookworm uses `/boot/firmware/`, not `/boot/`):

```
dtparam=spi=on
```

Reboot:

```bash
sudo reboot
```

Verify SPI is active:

```bash
ls /dev/spi*
# should show: /dev/spidev0.0  /dev/spidev0.1
```

---

## 3. SPI permissions

Allow your user to access SPI without `sudo`:

```bash
sudo usermod -a -G spi,gpio $USER
```

Log out and back in after running this. Without it, `run.py` will fail with a permission denied error on `/dev/spidev0.0`.

---

## Quick start (after SPI is set up)

Steps 4–13 below can be automated with the installer script:

```bash
bash install.sh
```

It installs system packages, creates a Python venv, downloads shapefiles, registers a systemd timer (10-minute refresh), and adds a `weathermap` shell command. Re-run it safely at any time — idempotent.

After installing, reload your shell and edit config if needed:

```bash
source ~/.bashrc
nano config.py          # set VCOM, location, and coordinates
weathermap run          # test once without the daemon
weathermap logs         # follow live output
```

The manual steps below remain useful as reference or if you prefer to set things up by hand.

---

## 4. System packages

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y \
    python3-pip \
    python3-venv \
    git \
    libopenblas-dev \
    libatlas-base-dev \
    libgeos-dev \
    libproj-dev \
    proj-data \
    proj-bin \
    libgdal-dev
```

`libgeos-dev`, `libproj-dev`, and `libgdal-dev` are required by Cartopy. Installing them as system packages avoids building from source.

---

## 5. Clone the project

```bash
git clone https://github.com/saryg/weathermap.git
cd weathermap
```

---

## 6. Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Bookworm enforces virtual environments for pip (PEP 668) — always activate the venv before installing or running.

Install dependencies:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

Cartopy can take several minutes to build on the 3B+.

---

## 7. IT8951 driver

```bash
pip install IT8951
```

No compatibility shim is needed on the 3B+ — `RPi.GPIO` supports the Broadcom GPIO natively.

---

## 8. Config

Copy the template and fill in your settings:

```bash
cp config.example.py config.py
nano config.py
```

**VCOM** — check the sticker on the ribbon cable of your display. It's a negative value, e.g. `-2.06`. This is unique to your panel.

```python
VCOM = -2.15  # check your display's ribbon cable sticker
```

**Your location:**

```python
WEATHER_LOCATION = "Dublin"
MAP_COUNTRY = "Ireland"

forecast_locations = {
    "Dublin": {
        "coords": [53.3498, -6.2603],
        "country": "Ireland",
        "region": "Dublin",   # county for Met Éireann warnings
    },
}
```

Add the location to `map_settings["Ireland"]["points_of_interest"]` too if you want it pinned on the map:

```python
map_settings = {
    "Ireland": {
        ...
        "points_of_interest": {
            "Dublin": [53.3498, -6.2603],
        },
        "forecast_location": "Dublin",
        ...
    },
}
```

---

## 9. Natural Earth shapefiles

Download the country boundary data into the project:

```bash
wget https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_0_map_units.zip
unzip ne_10m_admin_0_map_units.zip -d ne_10m_map_units/
rm ne_10m_admin_0_map_units.zip
```

---

## 10. Fonts and icons

- **Font** — `fonts/BebasNeue-Regular.ttf` (free on Google Fonts)
- **Icons** — `icons-transparent/` folder from the repo

---

## 11. Test the build (no display)

Verify the image builds correctly before connecting the screen:

```bash
python run.py --no-display
```

This fetches live data, renders the map, and saves `images/weathermap.bmp`.

The first run takes longer — it generates and caches the base map. Subsequent runs are faster.

---

## 12. Test sending to the display

Connect the HAT to the Pi's 40-pin header, then:

```bash
python run.py
```

If the image doesn't appear, try clearing the display first:

```bash
python send_to_display.py --clear
python send_to_display.py --file images/weathermap.bmp
```

---

## 13. Run as a daemon (systemd)

Use a systemd service and timer so the weathermap runs every 10 minutes, starts on boot, and logs to journald.

Create the service unit:

```bash
sudo nano /etc/systemd/system/weathermap.service
```

```ini
[Unit]
Description=Weathermap e-paper display
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=pi
WorkingDirectory=/home/pi/weathermap
ExecStart=/home/pi/weathermap/.venv/bin/python /home/pi/weathermap/run.py
StandardOutput=journal
StandardError=journal
```

Create the timer unit:

```bash
sudo nano /etc/systemd/system/weathermap.timer
```

```ini
[Unit]
Description=Update weathermap every 10 minutes

[Timer]
OnBootSec=30s
OnUnitActiveSec=10min
AccuracySec=10s

[Install]
WantedBy=timers.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable weathermap.timer
sudo systemctl start weathermap.timer
```

Check it's running:

```bash
sudo systemctl status weathermap.timer
```

View logs:

```bash
journalctl -u weathermap.service -f
```

---

## Troubleshooting

**SPI not found** — check `/dev/spidev0.0` exists. If not, re-run `raspi-config`, confirm SPI is enabled, and reboot.

**Permission denied on `/dev/spidev0.0`** — run `sudo usermod -a -G spi,gpio $USER`, then log out and back in.

**Wrong VCOM** — the display may flicker or show a washed-out image. Double-check the sticker on your ribbon cable and update `VCOM` in `config.py`.

**Cartopy projection errors** — make sure `libgeos-dev` and `libproj-dev` are apt-installed before `pip install`.

**Slow first run** — the 3B+ takes a few minutes to render the base map. This is normal. The pickle cache speeds up subsequent runs.

**Base map looks wrong after editing `config.py`** — delete the cached pickle to force a regeneration:

```bash
rm plots/*.pickle
python run.py --no-display
```
