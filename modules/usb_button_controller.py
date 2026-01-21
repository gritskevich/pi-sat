"""
USB Button Controller Module

Detects and handles USB device button events (rotary encoder + push button).
Designed for SENZER CS30 PC Speaker but works with any USB HID device.

Features:
- Rotary encoder detection (volume up/down)
- Push button detection (single/double press)
- Auto-reconnection on USB disconnect/reconnect (exponential backoff)
- Dynamic device path resolution (handles /dev/input/eventX changes)
- Independent module (no dependencies on other modules)
- Event-based callbacks

Research sources:
- Python evdev: https://python-evdev.readthedocs.io/en/latest/tutorial.html
- USB HID Consumer Control: https://github.com/neildavis/alsa_volume_from_usb_hid
- Single/Double press: https://circuitpython-button-handler.readthedocs.io/en/stable/
"""

import time
import threading
from typing import Callable, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

from modules.logging_utils import setup_logger, log_debug, log_warning

try:
    from evdev import InputDevice, categorize, ecodes, list_devices
    EVDEV_AVAILABLE = True
except ImportError:
    EVDEV_AVAILABLE = False


class ButtonAction(Enum):
    """Button action types"""
    SINGLE_PRESS = "single_press"
    DOUBLE_PRESS = "double_press"
    LONG_PRESS = "long_press"
    ROTATE_CW = "rotate_cw"  # Clockwise (volume up)
    ROTATE_CCW = "rotate_ccw"  # Counter-clockwise (volume down)
    # Consumer control keys (USB audio devices)
    VOLUME_UP = "volume_up"
    VOLUME_DOWN = "volume_down"
    PLAY_PAUSE = "play_pause"
    NEXT_TRACK = "next_track"
    PREV_TRACK = "prev_track"
    MUTE = "mute"


@dataclass
class ButtonEvent:
    """Button event data"""
    action: ButtonAction
    timestamp: float
    device_name: str
    raw_event: Optional[Any] = None


class USBButtonController:
    """
    USB Button Controller

    Monitors USB HID device for button events and triggers callbacks.
    Implements single/double press detection and rotary encoder support.
    """

    def __init__(
        self,
        device_path: Optional[str] = None,
        device_name_filter: Optional[str] = None,
        double_press_window: float = 0.4,
        debug: bool = False
    ):
        """
        Initialize USB button controller

        Args:
            device_path: Explicit device path (e.g., '/dev/input/event0')
            device_name_filter: Device name substring to filter (e.g., 'USB Audio')
            double_press_window: Max time between presses for double-press (seconds)
            debug: Enable debug logging
        """
        if not EVDEV_AVAILABLE:
            raise ImportError("evdev not available. Install: pip install evdev")

        self.device_path = device_path
        self.device_name_filter = device_name_filter
        self.double_press_window = double_press_window
        self.debug = debug
        self.logger = setup_logger(__name__, debug=debug)

        self.device: Optional[InputDevice] = None
        self.running = False
        self.monitor_thread: Optional[threading.Thread] = None

        # Button state tracking
        self.last_press_time: float = 0
        self.press_start_time: float = 0
        self.press_count: int = 0
        self.double_press_timer: Optional[threading.Timer] = None

        # Rotary encoder state
        self.last_rotary_value: Optional[int] = None

        # Consumer keys that should use press/release timing
        self.timed_consumer_keys = {164}  # KEY_PLAYPAUSE

        # Callbacks
        self.callbacks: Dict[ButtonAction, Callable] = {}
        self._warned_no_device = False

    def on(self, action: ButtonAction, callback: Callable[[ButtonEvent], None]):
        """Register callback for specific button action"""
        self.callbacks[action] = callback
        if self.debug:
            log_debug(self.logger, f"USB button callback registered: {action.value}")

    def find_device(self) -> Optional[str]:
        """
        Auto-detect USB device

        Returns:
            Device path if found, None otherwise
        """
        if not EVDEV_AVAILABLE:
            return None

        devices = [InputDevice(path) for path in list_devices()]

        if self.debug:
            log_debug(self.logger, "USB input devices:")
            for dev in devices:
                log_debug(self.logger, f"{dev.path}: {dev.name} ({dev.phys})")

        # Filter by name if specified
        if self.device_name_filter:
            for dev in devices:
                if self.device_name_filter.lower() in dev.name.lower():
                    if self.debug:
                        log_debug(self.logger, f"Found device: {dev.path} - {dev.name}")
                    return dev.path
            if self.debug:
                log_debug(self.logger, f"No device matched filter: {self.device_name_filter}")
            return None

        # Look for USB devices with button capabilities
        for dev in devices:
            if 'usb' in dev.phys.lower():
                caps = dev.capabilities(verbose=True)
                # Check if device has key/button capabilities
                if ('EV_KEY', ecodes.EV_KEY) in caps:
                    if self.debug:
                        log_debug(self.logger, f"Found USB device with buttons: {dev.path} - {dev.name}")
                    return dev.path

        return None

    def start(self) -> bool:
        """
        Start monitoring USB button

        Returns:
            True if started successfully, False otherwise
        """
        if self.running:
            if self.debug:
                log_debug(self.logger, "USB button controller already running")
            return True

        # Find device if not specified
        if not self.device_path:
            self.device_path = self.find_device()

        if not self.device_path:
            if not self._warned_no_device:
                log_warning(self.logger, "USB button device not found; retrying in background")
                self._warned_no_device = True
            if self.debug:
                log_debug(self.logger, "No USB button device found (will retry in background)")
            self.running = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            return True

        try:
            self.device = InputDevice(self.device_path)
            if self.debug:
                log_debug(self.logger, f"Opened device: {self.device.name}")
                log_debug(self.logger, f"Device capabilities: {self.device.capabilities()}")

            self.running = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()

            if self.debug:
                log_debug(self.logger, "USB button monitoring started")

            return True

        except Exception as e:
            if not self._warned_no_device:
                log_warning(self.logger, f"USB button device open failed; retrying in background ({e})")
                self._warned_no_device = True
            if self.debug:
                log_debug(self.logger, f"Error opening device: {e}")
            self.device = None
            self.running = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            return True

    def stop(self):
        """Stop monitoring USB button"""
        self.running = False

        if self.double_press_timer:
            self.double_press_timer.cancel()

        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)

        self._close_device()

        if self.debug:
            log_debug(self.logger, "USB button monitoring stopped")

    def _event_time(self, event) -> float:
        """Get event timestamp in seconds (fallback to wall time)."""
        try:
            return event.timestamp()
        except Exception:
            return time.time()

    def _close_device(self):
        """Close device handle safely"""
        if self.device:
            try:
                self.device.close()
            except Exception:
                pass
            self.device = None

    def _try_reconnect(self) -> bool:
        """
        Attempt to reconnect to USB device

        Returns:
            True if connected successfully, False otherwise
        """
        # Find device (supports dynamic path changes on reconnect)
        found_path = self.find_device()
        if not found_path:
            if self.debug:
                log_debug(self.logger, "Reconnect: Device not found")
            return False

        # Update path if it changed
        if self.device_path != found_path:
            if self.debug:
                log_debug(self.logger, f"Reconnect: Device path changed {self.device_path} → {found_path}")
            self.device_path = found_path

        try:
            self.device = InputDevice(self.device_path)
            if self.debug:
                log_debug(self.logger, f"Reconnected: {self.device.name} @ {self.device_path}")
            return True

        except Exception as e:
            if self.debug:
                log_debug(self.logger, f"Reconnect failed: {e}")
            return False

    def _monitor_loop(self):
        """Main event monitoring loop with auto-reconnection"""
        reconnect_delay = 1.0  # Start with 1 second
        max_reconnect_delay = 30.0  # Max 30 seconds between attempts

        while self.running:
            if not self.device:
                # Try to (re)connect
                if not self._try_reconnect():
                    time.sleep(reconnect_delay)
                    reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)
                    continue
                reconnect_delay = 1.0  # Reset on successful connection

            try:
                for event in self.device.read_loop():
                    if not self.running:
                        break
                    self._handle_event(event)

            except (OSError, IOError) as e:
                # Device disconnected or read error
                if self.debug:
                    log_debug(self.logger, f"Device disconnected or read error: {e}")
                self._close_device()
                # Will reconnect on next loop iteration
                time.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)

            except Exception as e:
                if self.debug:
                    log_debug(self.logger, f"Monitor loop error: {e}")
                self._close_device()
                time.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)

    def _handle_event(self, event):
        """Handle raw input event"""
        if self.debug:
            try:
                ts = event.timestamp()
                log_debug(
                    self.logger,
                    f"RAW event: {ts:.3f} type={event.type} code={event.code} value={event.value}"
                )
            except Exception:
                log_debug(
                    self.logger,
                    f"RAW event: type={event.type} code={event.code} value={event.value}"
                )
        # Button press/release events
        if event.type == ecodes.EV_KEY:
            self._handle_button_event(event)

        # Rotary encoder events (relative axis)
        elif event.type == ecodes.EV_REL:
            self._handle_rotary_event(event)

        # Absolute axis events (some rotary encoders)
        elif event.type == ecodes.EV_ABS:
            self._handle_rotary_event(event)

    def _handle_button_event(self, event):
        """Handle button press/release"""
        # event.value: 1 = press, 0 = release, 2 = hold

        # Check if this is a consumer control key
        if event.value == 1:  # Button pressed
            consumer_action = self._get_consumer_control_action(event.code)
            if consumer_action:
                if event.code in self.timed_consumer_keys:
                    self.press_start_time = self._event_time(event)
                    return
                self._trigger_action(consumer_action, event)
                if self.debug:
                    log_debug(self.logger, f"Consumer control: {consumer_action.value} (code: {event.code})")
                return  # Don't process as generic button
            if self.debug:
                key_name = ecodes.KEY.get(event.code, event.code)
                log_debug(self.logger, f"Unknown button code: {key_name} ({event.code})")

            # Generic button press
            self.press_start_time = self._event_time(event)
            if self.debug:
                log_debug(self.logger, f"Button pressed (code: {event.code})")

        elif event.value == 0:  # Button released
            # Handle timed consumer keys on release
            if event.code in self.timed_consumer_keys:
                press_duration = self._event_time(event) - self.press_start_time
                self._handle_short_press(event)
                return

            # Skip if it was a consumer control key
            if self._get_consumer_control_action(event.code):
                return

            press_duration = self._event_time(event) - self.press_start_time

            if self.debug:
                log_debug(self.logger, f"Button released (duration: {press_duration:.3f}s)")

            # Treat all releases as short press (single or double)
            self._handle_short_press(event)

    def _get_consumer_control_action(self, keycode: int) -> Optional[ButtonAction]:
        """Map consumer control key codes to actions"""
        # Consumer control key mappings
        consumer_keys = {
            113: ButtonAction.MUTE,           # KEY_MUTE
            114: ButtonAction.VOLUME_DOWN,    # KEY_VOLUMEDOWN
            115: ButtonAction.VOLUME_UP,      # KEY_VOLUMEUP
            163: ButtonAction.NEXT_TRACK,     # KEY_NEXTSONG
            164: ButtonAction.PLAY_PAUSE,     # KEY_PLAYPAUSE
            165: ButtonAction.PREV_TRACK,     # KEY_PREVIOUSSONG
        }
        return consumer_keys.get(keycode)

    def _handle_short_press(self, event):
        """Handle short button press (single or double)"""
        if self.double_press_window <= 0:
            self._trigger_action(ButtonAction.SINGLE_PRESS, event)
            return

        current_time = self._event_time(event)
        time_since_last = current_time - self.last_press_time

        # Cancel previous timer if exists
        if self.double_press_timer:
            self.double_press_timer.cancel()

        # Check if this could be a double press
        if time_since_last < self.double_press_window:
            self.press_count += 1
        else:
            self.press_count = 1

        self.last_press_time = current_time

        # Wait to see if another press comes
        if self.press_count == 1:
            self.double_press_timer = threading.Timer(
                self.double_press_window,
                lambda: self._trigger_action(ButtonAction.SINGLE_PRESS, event)
            )
            self.double_press_timer.start()

        elif self.press_count >= 2:
            if self.double_press_timer:
                self.double_press_timer.cancel()
            self._trigger_action(ButtonAction.DOUBLE_PRESS, event)
            self.press_count = 0

    def _handle_rotary_event(self, event):
        """Handle rotary encoder rotation"""
        # REL_WHEEL or REL_DIAL for rotary encoders
        if event.code in [ecodes.REL_WHEEL, ecodes.REL_DIAL, ecodes.REL_X, ecodes.REL_Y]:
            if event.value > 0:
                self._trigger_action(ButtonAction.ROTATE_CW, event)
            elif event.value < 0:
                self._trigger_action(ButtonAction.ROTATE_CCW, event)

            if self.debug:
                log_debug(self.logger, f"Rotary: {'CW' if event.value > 0 else 'CCW'} (value: {event.value})")

    def _trigger_action(self, action: ButtonAction, raw_event):
        """Trigger callback for action"""
        if action in self.callbacks:
            event = ButtonEvent(
                action=action,
                timestamp=time.time(),
                device_name=self.device.name if self.device else "unknown",
                raw_event=raw_event
            )

            if self.debug:
                log_debug(self.logger, f"Triggering action: {action.value}")

            try:
                self.callbacks[action](event)
            except Exception as e:
                if self.debug:
                    log_debug(self.logger, f"Callback error: {e}")


# Convenience factory function
def create_usb_button_controller(
    device_name_filter: str = "USB Audio",
    debug: bool = False
) -> USBButtonController:
    """
    Create and start USB button controller

    Args:
        device_name_filter: Device name substring to filter
        debug: Enable debug logging

    Returns:
        USBButtonController instance (started if device found)
    """
    controller = USBButtonController(
        device_name_filter=device_name_filter,
        debug=debug
    )
    controller.start()
    return controller
