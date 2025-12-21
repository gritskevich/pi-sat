#!/bin/bash
# Connection monitor - logs WiFi and USB mic status
# Usage: ./monitor_connections.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG="$PROJECT_ROOT/connection_monitor.log"

echo "=== Connection Monitor Started $(date) ===" | tee -a "$LOG"

while true; do
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

    # Check WiFi
    WIFI_STATUS=$(iwconfig wlan0 2>/dev/null | grep "ESSID" | grep -v "off/any")
    WIFI_POWER=$(iwconfig wlan0 2>/dev/null | grep "Power Management" | awk '{print $NF}')
    WIFI_QUALITY=$(iwconfig wlan0 2>/dev/null | grep "Link Quality" | awk '{print $2}')

    # Check USB Mic
    USB_MIC=$(lsusb | grep "1b3f:0004")

    if [ -z "$WIFI_STATUS" ]; then
        echo "[$TIMESTAMP] ⚠ WiFi DISCONNECTED!" | tee -a "$LOG"
    fi

    if [ -z "$USB_MIC" ]; then
        echo "[$TIMESTAMP] ⚠ USB MIC DISCONNECTED!" | tee -a "$LOG"
    fi

    # Log status every 30 seconds
    if [ $(($(date +%S) % 30)) -eq 0 ]; then
        echo "[$TIMESTAMP] WiFi: $WIFI_QUALITY PM:$WIFI_POWER | Mic: $(echo $USB_MIC | awk '{print $7" "$8}')" >> "$LOG"
    fi

    sleep 1
done
