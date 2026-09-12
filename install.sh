#!/bin/bash
# install.sh - Install dbus-esphome-grid-sensor on Venus OS
#
# This script installs the D-Bus grid service on a Venus OS device (Cerbo GX, Venus OS on Raspberry Pi, etc.)
# It sets up the service to run via daemontools (standard on Venus OS) or systemd.

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
# INSTALL_DIR lives under /data: Venus OS firmware updates restore /opt to
# factory defaults and would wipe the installation
INSTALL_DIR="/data/dbus-grid-service"
# Persistent service dir survives /service tmpfs wipes; linked into /service
SERVICE_DATA_DIR="/data/dbus-grid-service/service/dbus-grid-service"
SERVICE_DIR="/service/dbus-grid-service"
SERVICE_NAME="dbus-grid-service"
DBUS_INSTANCE="${DBUS_INSTANCE:-42}"
DEVICE_INSTANCE="${DEVICE_INSTANCE:-42}"
CUSTOM_NAME="${CUSTOM_NAME:-ESPHome CT Grid Sensor}"
MQTT_BROKER="${MQTT_BROKER:-localhost}"
MQTT_PORT="${MQTT_PORT:-1883}"
MQTT_USERNAME="${MQTT_USERNAME:-}"
MQTT_PASSWORD="${MQTT_PASSWORD:-}"
MQTT_TOPIC_PREFIX="${MQTT_TOPIC_PREFIX:-grid-sensor}"
RECONNECT_DELAY="${RECONNECT_DELAY:-5}"

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root"
        exit 1
    fi
}

check_venus_os() {
    if [[ ! -f /opt/victronenergy/version ]]; then
        log_warning "This doesn't appear to be a Venus OS system"
        log_warning "Installation will continue but may not work correctly"
    else
        log_info "Venus OS detected: $(cat /opt/victronenergy/version)"
    fi
}

check_python() {
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is not installed"
        exit 1
    fi

    python_version=$(python3 --version | cut -d' ' -f2)
    log_info "Python version: $python_version"
}

install_dependencies() {
    log_info "Verifying platform Python dependencies (no global package upgrades)..."
    python3 - <<'PYDEPS'
import sys
sys.path.insert(0, '/opt/victronenergy/dbus-systemcalc-py/ext/velib_python')
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
from vedbus import VeDbusService
from paho.mqtt.enums import CallbackAPIVersion
PYDEPS
}

create_install_dir() {
    log_info "Creating installation directory: $INSTALL_DIR"
    mkdir -p "$INSTALL_DIR"
}

copy_files() {
    log_info "Copying service files..."

    # Get the directory where this script is located
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    # Copy Python service
    cp "$SCRIPT_DIR/src/dbus_grid_service.py" "$INSTALL_DIR/"

    cp "$SCRIPT_DIR/src/service_launcher.py" "$INSTALL_DIR/"

    # Preserve existing settings during upgrades.
    if [ ! -f "$INSTALL_DIR/.env" ]; then
    # Keep spaces, quotes and shell-like characters as literal configuration.
    MQTT_BROKER="$MQTT_BROKER" MQTT_PORT="$MQTT_PORT" \
    MQTT_USERNAME="$MQTT_USERNAME" MQTT_PASSWORD="$MQTT_PASSWORD" \
    MQTT_TOPIC_PREFIX="$MQTT_TOPIC_PREFIX" DBUS_INSTANCE="$DBUS_INSTANCE" \
    DEVICE_INSTANCE="$DEVICE_INSTANCE" CUSTOM_NAME="$CUSTOM_NAME" \
    PYTHONPATH="${PYTHONPATH:-}" RECONNECT_DELAY="$RECONNECT_DELAY" \
    python3 - "$INSTALL_DIR/.env" <<'PYENV'
import json
import os
import sys

keys = ("MQTT_BROKER", "MQTT_PORT", "MQTT_USERNAME", "MQTT_PASSWORD",
        "MQTT_TOPIC_PREFIX", "DBUS_INSTANCE", "DEVICE_INSTANCE", "CUSTOM_NAME",
        "PYTHONPATH", "RECONNECT_DELAY")
with open(sys.argv[1], "w", encoding="utf-8") as config:
    for key in keys:
        config.write(key + "=" + json.dumps(os.environ[key], ensure_ascii=False) + "\n")
PYENV
    fi
    chmod 600 "$INSTALL_DIR/.env"

    log_success "Configuration written to $INSTALL_DIR/.env"
}

create_daemontools_service() {
    log_info "Creating daemontools service at $SERVICE_DATA_DIR..."

    local staging
    staging=$(mktemp -d "$INSTALL_DIR/service-stage.XXXXXX")
    mkdir -p "$staging/log"

    # Create run script
    cat > "$staging/run" <<EOF
#!/bin/sh
# daemontools run script for dbus-grid-service
exec 2>&1

# The firmware owns the system bus. Retry safely while it starts.
[ -S /var/run/dbus/system_bus_socket ] || { sleep 5; exit 1; }

# Change to install directory
cd $INSTALL_DIR || exit 1

# Run the service
exec python3 service_launcher.py
EOF

    chmod +x "$staging/run"

    # Log pair (multilog — svlogd does not exist on Venus OS)
    cat > "$staging/log/run" <<'EOF'
#!/bin/sh
exec 2>&1
mkdir -p /var/log/dbus-grid-service
exec multilog t s25000 n4 /var/log/dbus-grid-service
EOF
    chmod +x "$staging/log/run"

    # Preserve existing service/log directories and their supervisor state.
    # Stage and atomically replace scripts, never copy FIFO/lock files.
    mkdir -p "$(dirname "$SERVICE_DATA_DIR")"
    if [[ -d "$SERVICE_DIR" && ! -L "$SERVICE_DIR" ]]; then
        if [ -e "$SERVICE_DATA_DIR" ]; then
            rm -rf "$staging"
            log_error "Conflicting legacy and persistent service directories; preserve both for review"
            return 1
        fi
        svc -d "$SERVICE_DIR" 2>/dev/null || true
        mv "$SERVICE_DIR" "$SERVICE_DATA_DIR"
    fi
    mkdir -p "$SERVICE_DATA_DIR/log"
    svc -d "$SERVICE_DIR" 2>/dev/null || true
    mv "$staging/run" "$SERVICE_DATA_DIR/run"
    mv "$staging/log/run" "$SERVICE_DATA_DIR/log/run"
    rmdir "$staging/log" "$staging"
    if [ "$SKIP_START" = true ]; then
        touch "$SERVICE_DATA_DIR/down"
    else
        rm -f "$SERVICE_DATA_DIR/down"
    fi
    ln -sfn "$SERVICE_DATA_DIR" "$SERVICE_DIR"
    svc -t "$SERVICE_DIR/log" 2>/dev/null || true
    svc -u "$SERVICE_DIR/log" 2>/dev/null || true
    cat > "$INSTALL_DIR/boot.sh" <<'BOOT'
#!/bin/sh
[ -x /data/dbus-grid-service/service/dbus-grid-service/run ] || exit 0
ln -sfn /data/dbus-grid-service/service/dbus-grid-service /service/dbus-grid-service
BOOT
    chmod +x "$INSTALL_DIR/boot.sh"
    python3 - <<'PYBOOT'
from pathlib import Path
path = Path('/data/rc.local')
lines = path.read_text().splitlines() if path.exists() else ['#!/bin/sh']
command = '/data/dbus-grid-service/boot.sh'
lines = [line for line in lines if line != command]
index = next((i for i, line in enumerate(lines) if line.strip() == 'exit 0'), len(lines))
lines.insert(index, command)
path.write_text('\n'.join(lines) + '\n')
path.chmod(path.stat().st_mode | 0o111)
PYBOOT

    log_success "daemontools service created at $SERVICE_DIR -> $SERVICE_DATA_DIR"
}

create_systemd_service() {
    log_info "Creating systemd service..."

    cat > "/etc/systemd/system/$SERVICE_NAME.service" <<EOF
[Unit]
Description=D-Bus Grid Sensor Service for Venus OS
After=network.target dbus.service mosquitto.service
Wants=network.target dbus.service

[Service]
Type=simple
EnvironmentFile=$INSTALL_DIR/.env
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/python3 service_launcher.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=dbus-grid-service

# D-Bus access
Environment=DBUS_SYSTEM_BUS_ADDRESS=unix:path=/var/run/dbus/system_bus_socket

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable "$SERVICE_NAME"

    log_success "systemd service created and enabled"
}

verify_installation() {
    log_info "Verifying installation..."

    # Check files exist
    if [[ ! -f "$INSTALL_DIR/dbus_grid_service.py" ]]; then
        log_error "Service file not found at $INSTALL_DIR/dbus_grid_service.py"
        return 1
    fi

    if [[ ! -f "$INSTALL_DIR/.env" ]]; then
        log_error "Environment file not found at $INSTALL_DIR/.env"
        return 1
    fi

    # Test Python syntax
    if python3 -m py_compile "$INSTALL_DIR/dbus_grid_service.py"; then
        log_success "Python syntax check passed"
    else
        log_error "Python syntax check failed"
        return 1
    fi

    # Check daemontools service
    if [[ -f "$SERVICE_DIR/run" ]]; then
        log_success "daemontools service scripts exist"
    else
        log_warning "daemontools service not found (may use systemd instead)"
    fi

    # Check systemd service
    if [[ -f "/etc/systemd/system/$SERVICE_NAME.service" ]]; then
        log_success "systemd service file exists"
    fi

    return 0
}

start_service() {
    log_info "Starting service..."

    # Try daemontools first (Venus OS standard)
    if command -v svc &> /dev/null && [[ -d "$SERVICE_DIR" ]]; then
        local attempts=0
        until [ -p "$SERVICE_DIR/supervise/ok" ] || [ "$attempts" -ge 15 ]; do
            sleep 1
            attempts=$((attempts + 1))
        done
        svc -u "$SERVICE_DIR"
        sleep 2
        if svstat "$SERVICE_DIR" | grep -q "up"; then
            log_success "Service started via daemontools"
            return 0
        fi
    fi

    # Fall back to systemd
    if command -v systemctl &> /dev/null; then
        systemctl start "$SERVICE_NAME"
        sleep 2
        if systemctl is-active --quiet "$SERVICE_NAME"; then
            log_success "Service started via systemd"
            return 0
        fi
    fi

    log_error "Failed to start service"
    return 1
}

show_status() {
    echo
    log_info "=== Installation Summary ==="
    echo "Install directory: $INSTALL_DIR"
    echo "Service name: $SERVICE_NAME"
    echo "D-Bus instance: $DBUS_INSTANCE"
    echo "Device instance: $DEVICE_INSTANCE"
    echo "Custom name: $CUSTOM_NAME"
    echo "MQTT broker: $MQTT_BROKER:$MQTT_PORT"
    echo "MQTT topic prefix: $MQTT_TOPIC_PREFIX"
    echo

    log_info "=== Service Status ==="
    if command -v svc &> /dev/null && [[ -d "$SERVICE_DIR" ]]; then
        svstat "$SERVICE_DIR" 2>/dev/null || echo "daemontools: not running"
    fi

    if command -v systemctl &> /dev/null; then
        systemctl status "$SERVICE_NAME" --no-pager 2>/dev/null | head -10 || echo "systemd: not installed"
    fi

    echo
    log_info "=== Next Steps ==="
    echo "1. Verify D-Bus registration: dbus-spy com.victronenergy.grid.$DBUS_INSTANCE"
    echo "2. Check MQTT messages: mosquitto_sub -t '$MQTT_TOPIC_PREFIX/#' -v"
    echo "3. View logs: tail -f /var/log/dbus-grid-service/current (daemontools)"
    echo "   or: journalctl -u $SERVICE_NAME -f (systemd)"
    echo
    log_info "=== Configuration ==="
    echo "Edit $INSTALL_DIR/.env to change settings, then restart service:"
    echo "  svc -t $SERVICE_DIR  # daemontools"
    echo "  systemctl restart $SERVICE_NAME  # systemd"
}

main() {
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║     dbus-esphome-grid-sensor Venus OS Installer             ║"
    echo "║     ESP32 CT Grid Sensor → D-Bus Grid Meter                 ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"

    check_root
    check_venus_os
    check_python

    # Parse command line arguments
    SKIP_START=false
    USE_SYSTEMD=false

    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-deps)
                log_info "Platform dependencies are verified without installation"
                shift
                ;;
            --skip-start)
                SKIP_START=true
                shift
                ;;
            --systemd)
                USE_SYSTEMD=true
                shift
                ;;
            -h|--help)
                echo "Usage: $0 [options]"
                echo "Options:"
                echo "  --skip-deps    Skip dependency installation"
                echo "  --skip-start   Don't start service after install"
                echo "  --systemd      Use systemd instead of daemontools"
                echo "  -h, --help     Show this help"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done

    # --skip-deps remains accepted; platform imports are always verified.
    install_dependencies

    create_install_dir
    copy_files

    if [[ "$USE_SYSTEMD" == "true" ]]; then
        create_systemd_service
    else
        create_daemontools_service
    fi

    if verify_installation; then
        log_success "Installation verified successfully"

        if [[ "$SKIP_START" == "false" ]]; then
            start_service
        else
            log_info "Skipping service start (--skip-start specified)"
        fi

        show_status
    else
        log_error "Installation verification failed"
        exit 1
    fi
}

main "$@"
