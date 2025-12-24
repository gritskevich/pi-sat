#!/bin/bash
# Pi-Sat Daemon Installation Script
# Installs Pi-Sat as a systemd service for automatic startup and crash recovery

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_FILE="$SCRIPT_DIR/pi-sat.service"
SYSTEMD_DIR="/etc/systemd/system"
SERVICE_NAME="pi-sat.service"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: This script must be run with sudo${NC}"
    echo "Usage: sudo ./install-daemon.sh [install|uninstall|status]"
    exit 1
fi

# Get actual user (when using sudo)
ACTUAL_USER="${SUDO_USER:-$USER}"

install_daemon() {
    echo -e "${GREEN}Installing Pi-Sat daemon...${NC}"

    # Check if service file exists
    if [ ! -f "$SERVICE_FILE" ]; then
        echo -e "${RED}Error: Service file not found: $SERVICE_FILE${NC}"
        exit 1
    fi

    # Stop service if already running
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        echo "Stopping existing service..."
        systemctl stop "$SERVICE_NAME"
    fi

    # Copy service file to systemd directory
    echo "Installing service file..."
    cp "$SERVICE_FILE" "$SYSTEMD_DIR/$SERVICE_NAME"
    chmod 644 "$SYSTEMD_DIR/$SERVICE_NAME"

    # Reload systemd daemon
    echo "Reloading systemd..."
    systemctl daemon-reload

    # Enable service to start on boot
    echo "Enabling service..."
    systemctl enable "$SERVICE_NAME"

    # Start service
    echo "Starting service..."
    systemctl start "$SERVICE_NAME"

    # Show status
    sleep 2
    echo ""
    echo -e "${GREEN}✓ Pi-Sat daemon installed successfully!${NC}"
    echo ""
    echo "Service status:"
    systemctl status "$SERVICE_NAME" --no-pager -l
    echo ""
    echo -e "${YELLOW}Useful commands:${NC}"
    echo "  sudo systemctl start pi-sat    # Start service"
    echo "  sudo systemctl stop pi-sat     # Stop service"
    echo "  sudo systemctl restart pi-sat  # Restart service"
    echo "  sudo systemctl status pi-sat   # Check status"
    echo "  sudo journalctl -u pi-sat -f   # View live logs"
    echo "  sudo journalctl -u pi-sat -n 100  # View last 100 log lines"
    echo ""
}

uninstall_daemon() {
    echo -e "${YELLOW}Uninstalling Pi-Sat daemon...${NC}"

    # Stop service if running
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        echo "Stopping service..."
        systemctl stop "$SERVICE_NAME"
    fi

    # Disable service
    if systemctl is-enabled --quiet "$SERVICE_NAME"; then
        echo "Disabling service..."
        systemctl disable "$SERVICE_NAME"
    fi

    # Remove service file
    if [ -f "$SYSTEMD_DIR/$SERVICE_NAME" ]; then
        echo "Removing service file..."
        rm "$SYSTEMD_DIR/$SERVICE_NAME"
    fi

    # Reload systemd daemon
    echo "Reloading systemd..."
    systemctl daemon-reload

    echo -e "${GREEN}✓ Pi-Sat daemon uninstalled successfully!${NC}"
}

show_status() {
    echo -e "${GREEN}Pi-Sat Daemon Status:${NC}"
    echo ""
    systemctl status "$SERVICE_NAME" --no-pager -l || echo "Service not installed"
    echo ""
    echo -e "${YELLOW}Recent logs (last 20 lines):${NC}"
    journalctl -u "$SERVICE_NAME" -n 20 --no-pager || echo "No logs available"
}

# Main command handling
case "${1:-install}" in
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
        echo "Usage: sudo ./install-daemon.sh [install|uninstall|status]"
        echo ""
        echo "Commands:"
        echo "  install   - Install Pi-Sat as a system service (default)"
        echo "  uninstall - Remove Pi-Sat service"
        echo "  status    - Show service status and recent logs"
        exit 1
        ;;
esac
