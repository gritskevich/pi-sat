#!/bin/bash
# Mic Volume Adjustment Script for Pi-Sat
# Usage: ./scripts/adjust_mic_volume.sh [set|up|down|status] [value]
#
# Examples:
#   ./scripts/adjust_mic_volume.sh status        # Show current levels
#   ./scripts/adjust_mic_volume.sh set 80        # Set to 80%
#   ./scripts/adjust_mic_volume.sh up            # Increase by 5%
#   ./scripts/adjust_mic_volume.sh down          # Decrease by 5%

set -e

STEP=5  # Default step for up/down

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to get current mic volume
get_mic_volume() {
    # Try PulseAudio first (PipeWire compatibility)
    if command -v pactl &> /dev/null; then
        pactl list sources | grep -A 10 "Name.*input" | grep "Volume" | head -1 | awk '{print $5}' | tr -d '%'
    else
        # Fallback to ALSA
        amixer get Capture | grep -o '[0-9]*%' | head -1 | tr -d '%'
    fi
}

# Function to set mic volume (PulseAudio/PipeWire)
set_mic_volume_pulse() {
    local volume=$1
    # Get default source
    local source=$(pactl info | grep "Default Source" | cut -d: -f2 | xargs)
    if [ -n "$source" ]; then
        pactl set-source-volume "$source" "${volume}%"
        echo -e "${GREEN}✓${NC} Mic volume set to ${volume}%"
    else
        echo -e "${RED}✗${NC} Could not find default source"
        return 1
    fi
}

# Function to set mic volume (ALSA fallback)
set_mic_volume_alsa() {
    local volume=$1
    amixer set Capture "${volume}%" unmute > /dev/null 2>&1
    echo -e "${GREEN}✓${NC} Mic volume set to ${volume}% (ALSA)"
}

# Function to show current status
show_status() {
    echo -e "${YELLOW}=== Pi-Sat Mic Volume Status ===${NC}"
    echo ""

    # Current volume
    current=$(get_mic_volume)
    if [ -n "$current" ]; then
        echo -e "Current mic volume: ${GREEN}${current}%${NC}"
    else
        echo -e "${RED}Could not detect mic volume${NC}"
    fi

    # Show RMS recommendation
    echo ""
    echo -e "${YELLOW}Target RMS levels for good STT:${NC}"
    echo "  • Ideal: 500-1000 RMS"
    echo "  • Current typical: 250-300 RMS (too low)"
    echo "  • Recommendation: Increase mic volume to 70-80%"
    echo ""
    echo -e "${YELLOW}Test with:${NC} ./pi-sat.sh run_debug"
    echo "  Watch for RMS levels in wake word detection"
}

# Main logic
case "${1:-status}" in
    status)
        show_status
        ;;

    set)
        if [ -z "$2" ]; then
            echo -e "${RED}Error: Please specify volume level (0-100)${NC}"
            echo "Usage: $0 set <volume>"
            exit 1
        fi

        volume=$2
        if [ "$volume" -lt 0 ] || [ "$volume" -gt 100 ]; then
            echo -e "${RED}Error: Volume must be between 0-100${NC}"
            exit 1
        fi

        if command -v pactl &> /dev/null; then
            set_mic_volume_pulse "$volume"
        else
            set_mic_volume_alsa "$volume"
        fi
        show_status
        ;;

    up)
        current=$(get_mic_volume)
        if [ -z "$current" ]; then
            echo -e "${RED}Error: Could not detect current volume${NC}"
            exit 1
        fi

        new_volume=$((current + STEP))
        if [ "$new_volume" -gt 100 ]; then
            new_volume=100
        fi

        if command -v pactl &> /dev/null; then
            set_mic_volume_pulse "$new_volume"
        else
            set_mic_volume_alsa "$new_volume"
        fi
        show_status
        ;;

    down)
        current=$(get_mic_volume)
        if [ -z "$current" ]; then
            echo -e "${RED}Error: Could not detect current volume${NC}"
            exit 1
        fi

        new_volume=$((current - STEP))
        if [ "$new_volume" -lt 0 ]; then
            new_volume=0
        fi

        if command -v pactl &> /dev/null; then
            set_mic_volume_pulse "$new_volume"
        else
            set_mic_volume_alsa "$new_volume"
        fi
        show_status
        ;;

    *)
        echo -e "${RED}Error: Unknown command '$1'${NC}"
        echo ""
        echo "Usage: $0 [status|set|up|down] [value]"
        echo ""
        echo "Commands:"
        echo "  status       Show current mic volume and recommendations"
        echo "  set <vol>    Set mic volume to specific value (0-100)"
        echo "  up           Increase mic volume by 5%"
        echo "  down         Decrease mic volume by 5%"
        exit 1
        ;;
esac
