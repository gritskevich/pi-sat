#!/bin/bash
# Pi-Sat Daemon Installation Script
# Installs Pi-Sat as a systemd service for automatic startup and crash recovery

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_FILE="$SCRIPT_DIR/pi-sat.service"
SYSTEMD_DIR="/etc/systemd/system"
SERVICE_NAME="pi-sat.service"
SYSTEMCTL_PREFIX=()

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Defaults
ACTION="install"
MODE="system"  # system or user

# Parse args (supports: install|uninstall|status and --user/--system)
for arg in "$@"; do
    case "$arg" in
        install|uninstall|status)
            ACTION="$arg"
            ;;
        --user|user)
            MODE="user"
            ;;
        --system|system)
            MODE="system"
            ;;
        *)
            ;;
    esac
done

require_root() {
    if [ "$EUID" -ne 0 ]; then
        echo -e "${RED}Error: This action requires sudo${NC}"
        echo "Usage: sudo ./install-daemon.sh [install|uninstall|status] [--system]"
        exit 1
    fi
}

init_paths() {
    if [ "$MODE" = "user" ]; then
        if [ "$EUID" -eq 0 ]; then
            TARGET_USER="${SUDO_USER:-}"
            if [ -z "$TARGET_USER" ]; then
                echo -e "${RED}Error: user mode requires a real user (run without sudo)${NC}"
                exit 1
            fi
            USER_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"
            if [ -z "$USER_HOME" ]; then
                USER_HOME="/home/$TARGET_USER"
            fi
            USER_ID="$(id -u "$TARGET_USER")"
            RUNTIME_DIR="/run/user/$USER_ID"
            DBUS_ADDR="unix:path=$RUNTIME_DIR/bus"
            SYSTEMCTL_PREFIX=(runuser -u "$TARGET_USER" -- env XDG_RUNTIME_DIR="$RUNTIME_DIR" DBUS_SESSION_BUS_ADDRESS="$DBUS_ADDR" systemctl --user)
        else
            USER_HOME="$HOME"
            SYSTEMCTL_PREFIX=(systemctl --user)
        fi
        SYSTEMD_DIR="$USER_HOME/.config/systemd/user"
    else
        SYSTEMD_DIR="/etc/systemd/system"
        SYSTEMCTL_PREFIX=(systemctl)
    fi
}

systemctl_cmd() {
    "${SYSTEMCTL_PREFIX[@]}" "$@"
}

prepare_service_file() {
    if [ "$MODE" = "user" ]; then
        # User services must not set User=; strip it.
        TEMP_SERVICE="$(mktemp)"
        sed '/^User=/d' "$SERVICE_FILE" | sed 's/^WantedBy=multi-user.target$/WantedBy=default.target/' > "$TEMP_SERVICE"
        echo "$TEMP_SERVICE"
    else
        echo "$SERVICE_FILE"
    fi
}

install_daemon() {
    if [ "$MODE" = "system" ]; then
        require_root
    fi
    init_paths
    echo -e "${GREEN}Installing Pi-Sat daemon...${NC}"

    # Check if service file exists
    if [ ! -f "$SERVICE_FILE" ]; then
        echo -e "${RED}Error: Service file not found: $SERVICE_FILE${NC}"
        exit 1
    fi

    # Stop service if already running
    if systemctl_cmd is-active --quiet "$SERVICE_NAME"; then
        echo "Stopping existing service..."
        systemctl_cmd stop "$SERVICE_NAME"
    fi

    # Copy service file to systemd directory
    echo "Installing service file..."
    mkdir -p "$SYSTEMD_DIR"
    SERVICE_SRC="$(prepare_service_file)"
    cp "$SERVICE_SRC" "$SYSTEMD_DIR/$SERVICE_NAME"
    if [ "$MODE" = "user" ] && [ -n "${TEMP_SERVICE:-}" ]; then
        rm -f "$TEMP_SERVICE"
    fi
    chmod 644 "$SYSTEMD_DIR/$SERVICE_NAME"

    # Reload systemd daemon
    echo "Reloading systemd..."
    systemctl_cmd daemon-reload

    # Enable service to start on boot
    echo "Enabling service..."
    systemctl_cmd enable "$SERVICE_NAME"

    # Start service
    echo "Starting service..."
    systemctl_cmd start "$SERVICE_NAME"

    # Show status
    sleep 2
    echo ""
    echo -e "${GREEN}✓ Pi-Sat daemon installed successfully!${NC}"
    echo ""
    echo "Service status:"
    systemctl_cmd status "$SERVICE_NAME" --no-pager -l
    echo ""
    echo -e "${YELLOW}Useful commands:${NC}"
    if [ "$MODE" = "user" ]; then
        echo "  systemctl --user start pi-sat    # Start service"
        echo "  systemctl --user stop pi-sat     # Stop service"
        echo "  systemctl --user restart pi-sat  # Restart service"
        echo "  systemctl --user status pi-sat   # Check status"
        echo "  sudo journalctl _SYSTEMD_USER_UNIT=pi-sat.service -f   # View live logs (works even without user journal)"
        echo "  sudo journalctl _SYSTEMD_USER_UNIT=pi-sat.service -n 100  # Last 100 lines"
        echo "  # If user journal is enabled: journalctl --user -u pi-sat -f"
        echo "  sudo loginctl enable-linger $USER  # Start on boot"
    else
        echo "  sudo systemctl start pi-sat    # Start service"
        echo "  sudo systemctl stop pi-sat     # Stop service"
        echo "  sudo systemctl restart pi-sat  # Restart service"
        echo "  sudo systemctl status pi-sat   # Check status"
        echo "  sudo journalctl -u pi-sat -f   # View live logs"
        echo "  sudo journalctl -u pi-sat -n 100  # View last 100 log lines"
    fi
    echo ""

    # Warn if the other service scope is enabled to avoid double runs
    if [ "$MODE" = "user" ]; then
        if systemctl is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then
            echo -e "${YELLOW}Warning:${NC} system service is enabled; disable it to avoid double runs:"
            echo "  sudo systemctl disable --now pi-sat"
            echo ""
        fi
    else
        if systemctl --user is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then
            echo -e "${YELLOW}Warning:${NC} user service is enabled; disable it to avoid double runs:"
            echo "  systemctl --user disable --now pi-sat"
            echo ""
        fi
    fi
}

uninstall_daemon() {
    if [ "$MODE" = "system" ]; then
        require_root
    fi
    init_paths
    echo -e "${YELLOW}Uninstalling Pi-Sat daemon...${NC}"

    # Stop service if running
    if systemctl_cmd is-active --quiet "$SERVICE_NAME"; then
        echo "Stopping service..."
        systemctl_cmd stop "$SERVICE_NAME"
    fi

    # Disable service
    if systemctl_cmd is-enabled --quiet "$SERVICE_NAME"; then
        echo "Disabling service..."
        systemctl_cmd disable "$SERVICE_NAME"
    fi

    # Remove service file
    if [ -f "$SYSTEMD_DIR/$SERVICE_NAME" ]; then
        echo "Removing service file..."
        rm "$SYSTEMD_DIR/$SERVICE_NAME"
    fi

    # Reload systemd daemon
    echo "Reloading systemd..."
    systemctl_cmd daemon-reload

    echo -e "${GREEN}✓ Pi-Sat daemon uninstalled successfully!${NC}"
}

show_status() {
    if [ "$MODE" = "system" ]; then
        require_root
    fi
    init_paths
    echo -e "${GREEN}Pi-Sat Daemon Status:${NC}"
    echo ""
    systemctl_cmd status "$SERVICE_NAME" --no-pager -l || echo "Service not installed"
    echo ""
    echo -e "${YELLOW}Recent logs (last 20 lines):${NC}"
    if [ "$MODE" = "user" ]; then
        journalctl _SYSTEMD_USER_UNIT="$SERVICE_NAME" -n 20 --no-pager || echo "No logs available"
    else
        journalctl -u "$SERVICE_NAME" -n 20 --no-pager || echo "No logs available"
    fi
}

# Main command handling
case "$ACTION" in
    install)
        install_daemon
        ;;
    uninstall)
        uninstall_daemon
        ;;
    status)
        show_status
        ;;
    *)
        echo "Usage: ./install-daemon.sh [install|uninstall|status] [--user|--system]"
        echo ""
        echo "Commands:"
        echo "  install   - Install Pi-Sat as a system service (default)"
        echo "  uninstall - Remove Pi-Sat service"
        echo "  status    - Show service status and recent logs"
        echo ""
        echo "Options:"
        echo "  --user    - Install as user service (recommended for audio)"
        echo "  --system  - Install as system service (default)"
        exit 1
        ;;
esac
