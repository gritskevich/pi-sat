"""
USB Button Router

Maps USB button events to control events on the internal event bus.
Keeps USBButtonController focused on input only (single responsibility).
"""

from typing import Optional

import config
from modules.base_module import BaseModule
from modules.control_events import (
    ControlEvent,
    EVENT_BUTTON_PRESSED,
    EVENT_BUTTON_DOUBLE_PRESSED,
    EVENT_VOLUME_UP_REQUESTED,
    EVENT_VOLUME_DOWN_REQUESTED,
)
from modules.logging_utils import setup_logger, log_warning, log_debug
from modules.usb_button_controller import USBButtonController, ButtonAction, ButtonEvent, EVDEV_AVAILABLE


class USBButtonRouter(BaseModule):
    """
    Routes USB button events to the internal EventBus.
    """

    def __init__(
        self,
        controller: USBButtonController,
        event_bus,
        debug: bool = False,
    ):
        super().__init__(__name__, debug=debug, event_bus=event_bus)
        self.controller = controller

        self._register_callbacks()

    def _register_callbacks(self):
        self.controller.on(ButtonAction.VOLUME_UP, self._on_volume_up)
        self.controller.on(ButtonAction.VOLUME_DOWN, self._on_volume_down)
        self.controller.on(ButtonAction.ROTATE_CW, self._on_volume_up)
        self.controller.on(ButtonAction.ROTATE_CCW, self._on_volume_down)
        self.controller.on(ButtonAction.PLAY_PAUSE, self._on_play_pause)
        self.controller.on(ButtonAction.SINGLE_PRESS, self._on_play_pause)
        self.controller.on(ButtonAction.DOUBLE_PRESS, self._on_next_track)
        self.controller.on(ButtonAction.NEXT_TRACK, self._on_next_track)

    def start(self) -> bool:
        return self.controller.start()

    def stop(self):
        self.controller.stop()

    def _on_volume_up(self, event: ButtonEvent):
        self.event_bus.publish(
            ControlEvent.now(EVENT_VOLUME_UP_REQUESTED, source="usb_button")
        )

    def _on_volume_down(self, event: ButtonEvent):
        self.event_bus.publish(
            ControlEvent.now(EVENT_VOLUME_DOWN_REQUESTED, source="usb_button")
        )

    def _on_play_pause(self, event: ButtonEvent):
        self.event_bus.publish(
            ControlEvent.now(EVENT_BUTTON_PRESSED, source="usb_button")
        )

    def _on_next_track(self, event: ButtonEvent):
        self.event_bus.publish(
            ControlEvent.now(EVENT_BUTTON_DOUBLE_PRESSED, source="usb_button")
        )


def create_usb_button_router(event_bus, debug: bool = False) -> Optional[USBButtonRouter]:
    """
    Create USB button controller + router.

    Returns None if evdev is unavailable or device open fails.
    """
    logger = setup_logger(__name__, debug=debug)
    if not EVDEV_AVAILABLE:
        log_warning(logger, "USB button disabled: evdev not available")
        return None

    controller = USBButtonController(
        device_path=config.USB_BUTTON_DEVICE_PATH,
        device_name_filter=config.USB_BUTTON_DEVICE_FILTER,
        double_press_window=config.USB_BUTTON_DOUBLE_PRESS_WINDOW,
        debug=config.USB_BUTTON_DEBUG or debug
    )
    router = USBButtonRouter(
        controller=controller,
        event_bus=event_bus,
        debug=config.USB_BUTTON_DEBUG or debug
    )
    if not router.start():
        log_warning(logger, "USB button disabled: device not found or not readable")
        return None
    log_debug(logger, "USB button router started")
    return router
