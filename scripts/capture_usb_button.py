#!/usr/bin/env python3
import argparse
import time

try:
    from evdev import InputDevice, list_devices, ecodes
except ImportError as exc:
    raise SystemExit("evdev not available. Install: pip install evdev") from exc


def pick_device(filter_text: str | None) -> InputDevice:
    devices = [InputDevice(path) for path in list_devices()]
    if filter_text:
        for dev in devices:
            if filter_text.lower() in dev.name.lower():
                return dev
    if not devices:
        raise SystemExit("No input devices found")
    return devices[0]


def main() -> None:
    parser = argparse.ArgumentParser(description="Minimal USB button event capture")
    parser.add_argument("--device", help="Device path (e.g., /dev/input/event2)")
    parser.add_argument("--filter", help="Substring match for device name")
    args = parser.parse_args()

    if args.device:
        dev = InputDevice(args.device)
    else:
        dev = pick_device(args.filter)

    print(f"Using device: {dev.path} - {dev.name}")
    print("Press buttons. Ctrl+C to stop.")

    for event in dev.read_loop():
        ts = event.timestamp()
        timestamp = time.strftime("%H:%M:%S", time.localtime(ts))
        timestamp = f"{timestamp}.{int((ts % 1) * 1000):03d}"
        event_type = ecodes.EV.get(event.type, event.type)
        code = event.code
        if event.type == ecodes.EV_KEY:
            code = ecodes.KEY.get(event.code, event.code)
        elif event.type == ecodes.EV_REL:
            code = ecodes.REL.get(event.code, event.code)
        elif event.type == ecodes.EV_ABS:
            code = ecodes.ABS.get(event.code, event.code)
        elif event.type == ecodes.EV_MSC:
            code = ecodes.MSC.get(event.code, event.code)
        print(f"{timestamp} {event_type} {code} value={event.value}")


if __name__ == "__main__":
    main()
