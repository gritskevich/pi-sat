#!/usr/bin/env python3
import argparse
import select
import time
try:
    from evdev import InputDevice, list_devices
except ImportError as exc:
    raise SystemExit("evdev not available. Install: pip install evdev") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture raw input events")
    parser.add_argument(
        "--device",
        default="/dev/input/event0",
        help="Input device path (default: /dev/input/event0)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Capture from all devices instead of a single device",
    )
    parser.add_argument("--seconds", type=float, default=60.0, help="Capture duration")
    args = parser.parse_args()

    if args.all:
        devices = [InputDevice(path) for path in list_devices()]
        if not devices:
            raise SystemExit("No input devices found")
    else:
        devices = [InputDevice(args.device)]

    print("Capturing from devices:")
    for dev in devices:
        print(f"  {dev.path} - {dev.name}")
    print("Press buttons. Ctrl+C to stop.")

    fd_to_dev = {dev.fd: dev for dev in devices}
    end = time.time() + args.seconds

    try:
        while time.time() < end:
            ready, _, _ = select.select(list(fd_to_dev.keys()), [], [], 0.5)
            for fd in ready:
                dev = fd_to_dev[fd]
                for event in dev.read():
                    print(
                        f"{dev.path} sec={event.sec} usec={event.usec} "
                        f"type={event.type} code={event.code} value={event.value}"
                    )
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
