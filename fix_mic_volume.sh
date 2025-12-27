#!/bin/bash
# Fix microphone volume levels (run after boot or when mics are plugged in)

echo "Setting microphone input volumes to 30%..."

# USB Microphone (MUSIC-BOOST MB-306)
pactl set-source-volume alsa_input.usb-MUSIC-BOOST_USB_Microphone_MB-306-00.mono-fallback 30% 2>/dev/null && \
    echo "✓ USB Microphone → 30%" || echo "✗ USB Microphone not found"

# USB Composite Device (Jieli)
pactl set-source-volume alsa_input.usb-Jieli_Technology_USB_Composite_Device_4250323230333208-01.mono-fallback 30% 2>/dev/null && \
    echo "✓ USB Composite Device → 30%" || echo "✗ USB Composite Device not found"

echo ""
echo "Current volumes:"
pactl list sources | grep -A 3 "Description.*USB" | grep -E "Description:|Volume:"
