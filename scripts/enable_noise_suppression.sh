#!/bin/bash

set -e

if ! command -v pactl >/dev/null 2>&1; then
    echo "pactl not found. Install PipeWire/PulseAudio tools first."
    exit 1
fi

DEFAULT_SOURCE="$(pactl get-default-source 2>/dev/null || true)"
if [ -z "$DEFAULT_SOURCE" ]; then
    DEFAULT_SOURCE="$(pactl info | awk -F': ' '/Default Source/ {print $2; exit}')"
fi

if [ -z "$DEFAULT_SOURCE" ]; then
    echo "Could not determine default source."
    exit 1
fi

# Unload any existing echo-cancel modules (avoid duplicates)
for id in $(pactl list short modules | awk '$2=="module-echo-cancel" {print $1}'); do
    pactl unload-module "$id" || true
done

MODULE_ID="$(pactl load-module module-echo-cancel \
    aec_method=webrtc \
    source_master="$DEFAULT_SOURCE" \
    source_name="pi_sat_ns" \
    sink_name="pi_sat_ns_out" \
    source_properties="device.description=PiSat-NS" \
    sink_properties="device.description=PiSat-NS-OUT")"

echo "Loaded noise suppression module: $MODULE_ID"
echo "New source: pi_sat_ns (description: PiSat-NS)"
echo "Set INPUT_DEVICE_NAME=PiSat-NS before running Pi-Sat."
