import time

from modules.control_events import (
    EVENT_BUTTON_PRESSED,
    EVENT_BUTTON_DOUBLE_PRESSED,
    EVENT_VOLUME_UP_REQUESTED,
    EVENT_VOLUME_DOWN_REQUESTED,
)
from modules.usb_button_controller import ButtonAction, ButtonEvent
from modules.usb_button_router import USBButtonRouter


class FakeController:
    def __init__(self):
        self.callbacks = {}
        self.started = False

    def on(self, action, callback):
        self.callbacks[action] = callback

    def start(self):
        self.started = True
        return True

    def stop(self):
        self.started = False

    def emit(self, action):
        callback = self.callbacks.get(action)
        if callback:
            callback(ButtonEvent(action=action, timestamp=time.time(), device_name="fake"))


class FakeEventBus:
    def __init__(self):
        self.events = []

    def publish(self, event):
        self.events.append(event)


def test_usb_button_volume_controls():
    controller = FakeController()
    bus = FakeEventBus()
    router = USBButtonRouter(controller, bus)

    controller.emit(ButtonAction.VOLUME_UP)
    controller.emit(ButtonAction.VOLUME_DOWN)

    assert bus.events[0].name == EVENT_VOLUME_UP_REQUESTED
    assert bus.events[1].name == EVENT_VOLUME_DOWN_REQUESTED


def test_usb_button_play_pause_toggle():
    controller = FakeController()
    bus = FakeEventBus()
    router = USBButtonRouter(controller, bus)

    controller.emit(ButtonAction.PLAY_PAUSE)
    assert bus.events[-1].name == EVENT_BUTTON_PRESSED


def test_usb_button_multiple_presses_emit_events():
    controller = FakeController()
    bus = FakeEventBus()
    router = USBButtonRouter(controller, bus)

    controller.emit(ButtonAction.PLAY_PAUSE)
    controller.emit(ButtonAction.PLAY_PAUSE)

    router.stop()

    assert len(bus.events) == 2
    assert bus.events[0].name == EVENT_BUTTON_PRESSED
    assert bus.events[1].name == EVENT_BUTTON_PRESSED


def test_usb_button_double_press_action_next():
    controller = FakeController()
    bus = FakeEventBus()
    router = USBButtonRouter(controller, bus)

    controller.emit(ButtonAction.DOUBLE_PRESS)

    assert bus.events[-1].name == EVENT_BUTTON_DOUBLE_PRESSED
