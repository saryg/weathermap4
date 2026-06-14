# Setup Guide — Waveshare 9.7" E-Paper

Raspberry Pi 3B+ · Debian Trixie 64-bit Lite · Waveshare 9.7" e-Paper HAT (IT8951).

---

## 1. Enable SPI

```bash
sudo raspi-config
```

**Interface Options → SPI → Enable**, then reboot.

Verify:

```bash
ls /dev/spi*
# /dev/spidev0.0  /dev/spidev0.1
```

---

## 2. SPI permissions

```bash
sudo usermod -a -G spi,gpio $USER
```

Log out and back in.

---

## 3. Install

```bash
git clone https://github.com/saryg/weathermap4.git
cd weathermap4
bash install.sh
source ~/.bashrc
```

---

## 4. Config

```bash
nano config.py
```

**VCOM** — negative value on the sticker of your display's ribbon cable:

```python
VCOM = -2.15
```

**Location:**

```python
WEATHER_LOCATION = "Dublin"
MAP_COUNTRY = "Ireland"

forecast_locations = {
    "Dublin": {
        "coords": [53.3498, -6.2603],
        "country": "Ireland",
        "region": "Dublin",
    },
}
```

Your location is automatically pinned on the map — no need to edit `map_settings`.

---

## 5. Test

```bash
weathermap run --no-display   # renders to images/weathermap.bmp
weathermap run                # sends to display
weathermap logs               # live output
```

---

## Manual setup reference

<details>
<summary>Expand if not using the installer</summary>

### System packages

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y \
    python3-pip python3-venv python3-dev git \
    libopenblas-dev \
    libgeos-dev libproj-dev proj-data proj-bin libgdal-dev
```

### Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install IT8951
```

### Shapefiles

Downloaded automatically by the installer, or manually:

```bash
wget https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_0_map_units.zip
unzip ne_10m_admin_0_map_units.zip -d ne_10m_map_units/
rm ne_10m_admin_0_map_units.zip
```

### Fonts and icons

- `fonts/BebasNeue-Regular.ttf` (free on Google Fonts)
- `icons-transparent/` folder from the repo

### Systemd timer

`/etc/systemd/system/weathermap.service`:

```ini
[Unit]
Description=Weathermap e-paper display
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=pi
WorkingDirectory=/home/pi/weathermap4
ExecStart=/home/pi/weathermap4/.venv/bin/python /home/pi/weathermap4/run.py
StandardOutput=journal
StandardError=journal
```

`/etc/systemd/system/weathermap.timer`:

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

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now weathermap.timer
```

</details>
