#!/usr/bin/env python3
import argparse
import select
import time

try:
    from evdev import InputDevice, ecodes
except ImportError as exc:
    raise SystemExit("evdev not available. Install: pip install evdev") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture USB button events for 30s")
    parser.add_argument(
        "--device",
        default="/dev/input/event0",
        help="Input device path",
    )
    parser.add_argument("--seconds", type=float, default=30.0, help="Capture duration")
    args = parser.parse_args()

    dev = InputDevice(args.device)
    print(f"Capturing {args.seconds:.0f}s on {dev.path} ({dev.name})")

    end = time.time() + args.seconds
    while time.time() < end:
        ready, _, _ = select.select([dev.fd], [], [], 0.5)
        if not ready:
            continue
        for event in dev.read():
            if event.type == ecodes.EV_KEY:
                key = ecodes.KEY.get(event.code, event.code)
                print(f"{time.time():.3f} KEY {key} value={event.value}")
            elif event.type == ecodes.EV_REL:
                rel = ecodes.REL.get(event.code, event.code)
                print(f"{time.time():.3f} REL {rel} value={event.value}")


if __name__ == "__main__":
    main()
