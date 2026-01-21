import pytest
from unittest.mock import Mock, patch, MagicMock

try:
    from evdev import ecodes
except Exception:  # pragma: no cover - evdev not available
    ecodes = None

from modules.usb_button_controller import USBButtonController, ButtonAction


class FakeEvent:
    def __init__(self, ts: float, value: int, code: int = 164, type_: int = None):
        self._ts = ts
        self.value = value
        self.code = code
        self.type = ecodes.EV_KEY if type_ is None else type_

    def timestamp(self) -> float:
        return self._ts


@pytest.mark.skipif(ecodes is None, reason="evdev not available")
def test_play_pause_short_press_triggers_single():
    controller = USBButtonController(
        device_path="/dev/input/event0",
        double_press_window=0,
        debug=False,
    )
    actions = []
    controller.on(ButtonAction.SINGLE_PRESS, lambda event: actions.append(event.action))

    controller._handle_button_event(FakeEvent(0.000, 1))
    controller._handle_button_event(FakeEvent(0.015, 0))

    assert actions == [ButtonAction.SINGLE_PRESS]


@pytest.mark.skipif(ecodes is None, reason="evdev not available")
def test_close_device_safely_handles_none():
    controller = USBButtonController(device_path="/dev/input/event0", debug=False)
    controller.device = None
    controller._close_device()  # Should not raise
    assert controller.device is None


@pytest.mark.skipif(ecodes is None, reason="evdev not available")
def test_close_device_closes_open_device():
    controller = USBButtonController(device_path="/dev/input/event0", debug=False)
    mock_device = Mock()
    controller.device = mock_device

    controller._close_device()

    mock_device.close.assert_called_once()
    assert controller.device is None


@pytest.mark.skipif(ecodes is None, reason="evdev not available")
def test_close_device_handles_close_error():
    controller = USBButtonController(device_path="/dev/input/event0", debug=False)
    mock_device = Mock()
    mock_device.close.side_effect = OSError("Device error")
    controller.device = mock_device

    controller._close_device()  # Should not raise
    assert controller.device is None


@pytest.mark.skipif(ecodes is None, reason="evdev not available")
@patch('modules.usb_button_controller.InputDevice')
def test_try_reconnect_success(mock_input_device_class):
    controller = USBButtonController(
        device_name_filter="USB Audio",
        debug=False
    )
    controller.device_path = "/dev/input/event0"
    controller.device = None

    # Mock find_device to return a path
    controller.find_device = Mock(return_value="/dev/input/event1")

    # Mock InputDevice constructor
    mock_device = Mock()
    mock_device.name = "Test Device"
    mock_input_device_class.return_value = mock_device

    result = controller._try_reconnect()

    assert result is True
    assert controller.device == mock_device
    assert controller.device_path == "/dev/input/event1"


@pytest.mark.skipif(ecodes is None, reason="evdev not available")
def test_try_reconnect_device_not_found():
    controller = USBButtonController(
        device_name_filter="USB Audio",
        debug=False
    )
    controller.device = None

    # Mock find_device to return None
    controller.find_device = Mock(return_value=None)

    result = controller._try_reconnect()

    assert result is False
    assert controller.device is None


@pytest.mark.skipif(ecodes is None, reason="evdev not available")
@patch('modules.usb_button_controller.InputDevice')
def test_try_reconnect_handles_path_change(mock_input_device_class):
    controller = USBButtonController(debug=False)
    controller.device_path = "/dev/input/event0"
    controller.device = None

    # Device path changed after reconnect
    controller.find_device = Mock(return_value="/dev/input/event2")

    mock_device = Mock()
    mock_device.name = "Reconnected Device"
    mock_input_device_class.return_value = mock_device

    result = controller._try_reconnect()

    assert result is True
    assert controller.device_path == "/dev/input/event2"
    assert controller.device == mock_device


@pytest.mark.skipif(ecodes is None, reason="evdev not available")
@patch('modules.usb_button_controller.InputDevice')
def test_try_reconnect_fails_on_device_error(mock_input_device_class):
    controller = USBButtonController(debug=False)
    controller.device_path = "/dev/input/event0"
    controller.device = None

    controller.find_device = Mock(return_value="/dev/input/event0")
    mock_input_device_class.side_effect = OSError("Permission denied")

    result = controller._try_reconnect()

    assert result is False
    assert controller.device is None
