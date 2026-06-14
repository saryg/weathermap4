#!/usr/bin/env bash
# Weathermap installer for Raspberry Pi.
# Run from the project directory after cloning:
#   bash install.sh

set -euo pipefail

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info() { echo -e "${GREEN}[✓]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
die()  { echo -e "${RED}[✗]${NC} $*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
[[ "$(uname -s)" == "Linux" ]] || die "This installer is for Raspberry Pi / Linux only."
[[ $EUID -ne 0 ]]              || die "Do not run as root — run as your normal user (sudo is used where needed)."

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$PROJECT_DIR/.venv"
PYTHON="$VENV/bin/python"
SERVICE=weathermap

echo ""
echo "  Project: $PROJECT_DIR"
echo "  User:    $USER"
echo ""

# ---------------------------------------------------------------------------
# 1. System packages
# ---------------------------------------------------------------------------
info "Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y --no-install-recommends \
    python3-pip python3-venv python3-dev git \
    libopenblas-dev \
    libgeos-dev libproj-dev proj-data proj-bin libgdal-dev \
    wget unzip

# ---------------------------------------------------------------------------
# 2. Python virtual environment
# ---------------------------------------------------------------------------
if [[ ! -d "$VENV" ]]; then
    info "Creating virtual environment..."
    python3 -m venv "$VENV"
fi

info "Installing Python dependencies (cartopy can take several minutes on a Pi)..."
"$VENV/bin/pip" install --upgrade pip -q
"$VENV/bin/pip" install -r "$PROJECT_DIR/requirements.txt" -q

info "Installing IT8951 display driver..."
"$VENV/bin/pip" install IT8951 -q

# ---------------------------------------------------------------------------
# 3. Required directories
# ---------------------------------------------------------------------------
mkdir -p "$PROJECT_DIR/plots" "$PROJECT_DIR/images"
info "Directories ready."

# ---------------------------------------------------------------------------
# 3. Fonts
# ---------------------------------------------------------------------------
FONT="$PROJECT_DIR/fonts/BebasNeue-Regular.ttf"
if [[ -f "$FONT" ]]; then
    info "Font already present — skipping download."
else
    info "Downloading BebasNeue font..."
    wget -q "https://github.com/google/fonts/raw/main/ofl/bebasneue/BebasNeue-Regular.ttf" \
         -O "$PROJECT_DIR/fonts/BebasNeue-Regular.ttf"
    info "Font installed."
fi

# ---------------------------------------------------------------------------
# 4. Config
# ---------------------------------------------------------------------------
if [[ ! -f "$PROJECT_DIR/config.py" ]]; then
    cp "$PROJECT_DIR/config.example.py" "$PROJECT_DIR/config.py"
    warn "config.py created from template — edit it before your first run:"
    warn "  nano $PROJECT_DIR/config.py"
    warn "  Set VCOM to the value on your display's ribbon cable sticker."
    warn "  Set WEATHER_LOCATION, MAP_COUNTRY, and your coordinates."
fi

# ---------------------------------------------------------------------------
# 5. Natural Earth shapefiles
# ---------------------------------------------------------------------------
SHAPEFILES="$PROJECT_DIR/ne_10m_map_units/ne_10m_admin_0_map_units.shp"
if [[ -f "$SHAPEFILES" ]]; then
    info "Shapefiles already present — skipping download."
else
    info "Downloading shapefiles from naciscdn.org..."
    wget -q "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_0_map_units.zip" \
         -O /tmp/ne_10m_admin_0_map_units.zip
    mkdir -p "$PROJECT_DIR/ne_10m_map_units"
    unzip -q /tmp/ne_10m_admin_0_map_units.zip -d "$PROJECT_DIR/ne_10m_map_units"
    rm /tmp/ne_10m_admin_0_map_units.zip
    info "Shapefiles downloaded."
fi

# ---------------------------------------------------------------------------
# 6. Systemd service + timer (10-minute refresh)
# ---------------------------------------------------------------------------
info "Installing systemd units..."

sudo tee /etc/systemd/system/${SERVICE}.service > /dev/null << EOF
[Unit]
Description=Weathermap e-paper display update
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=$USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$PYTHON $PROJECT_DIR/run.py
StandardOutput=journal
StandardError=journal
EOF

sudo tee /etc/systemd/system/${SERVICE}.timer > /dev/null << EOF
[Unit]
Description=Update weathermap every 10 minutes

[Timer]
OnBootSec=30s
OnUnitActiveSec=10min
AccuracySec=10s

[Install]
WantedBy=timers.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE}.timer
sudo systemctl start ${SERVICE}.timer
info "Daemon enabled — weathermap will update every 10 minutes."

# ---------------------------------------------------------------------------
# 7. 'weathermap' shell command
# ---------------------------------------------------------------------------
BASHRC="$HOME/.bashrc"
MARKER="# weathermap-cli"

if grep -q "$MARKER" "$BASHRC" 2>/dev/null; then
    warn "'weathermap' command already in $BASHRC — skipping (re-run manually to update paths)."
else
    info "Adding 'weathermap' command to $BASHRC..."
    # $PROJECT_DIR and $PYTHON expand now (install-time paths embedded).
    # \$1, \${@:2} etc. are escaped so they remain as literals in .bashrc.
    cat >> "$BASHRC" << HEREDOC

$MARKER
weathermap() {
    local _dir="$PROJECT_DIR"
    local _py="$PYTHON"
    case "\$1" in
        start)
            sudo systemctl enable ${SERVICE}.timer
            sudo systemctl start  ${SERVICE}.timer
            echo "Weathermap started — refreshing every 10 minutes."
            ;;
        stop)
            sudo systemctl stop    ${SERVICE}.timer
            sudo systemctl disable ${SERVICE}.timer
            echo "Weathermap stopped."
            ;;
        run)    "\$_py" "\$_dir/run.py" \${@:2} ;;
        status) systemctl status ${SERVICE}.timer ${SERVICE}.service ;;
        logs)   journalctl -u ${SERVICE}.service -f ;;
        *)
            echo "Usage: weathermap {start|stop|run|status|logs}"
            echo "  start   — enable and start the 10-minute refresh timer"
            echo "  stop    — stop and disable the timer"
            echo "  run     — run once now (pass extra flags after 'run')"
            echo "  status  — show systemd timer and service status"
            echo "  logs    — follow live logs"
            ;;
    esac
}
HEREDOC
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
info "Installation complete."
echo ""
echo "  Reload your shell first:"
echo "    source ~/.bashrc"
echo ""
echo "  Then:"
echo "    weathermap run       — build and push to display once"
echo "    weathermap logs      — follow live refresh logs"
echo "    weathermap stop      — pause the 10-minute timer"
echo "    weathermap start     — resume the timer"
echo ""
if grep -q "MyCity" "$PROJECT_DIR/config.py" 2>/dev/null; then
    warn "config.py still has placeholder values — edit before running:"
    warn "  nano $PROJECT_DIR/config.py"
fi
