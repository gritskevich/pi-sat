import threading
import time

from modules.command_processor import CommandProcessor
from modules.command_validator import ValidationResult
from modules.control_events import ControlEvent, EVENT_BUTTON_PRESSED, EVENT_BUTTON_DOUBLE_PRESSED
from modules.event_bus import EventBus
from modules.player_event_router import PlayerEventRouter
from modules.playback_state_machine import PlaybackStateMachine
from modules.usb_button_router import USBButtonRouter
from modules.usb_button_controller import ButtonAction, ButtonEvent
from modules.interfaces import Intent


class FakeLibrary:
    def search_best(self, query):
        return ("maman.mp3", 0.9)


class FakeMPD:
    def __init__(self, state="pause"):
        self.state = state
        self.calls = []
        self.resume_event = threading.Event()
        self.play_event = threading.Event()
        self.next_event = threading.Event()
        self._library = FakeLibrary()

    def get_music_library(self):
        return self._library

    def get_status(self):
        return {"state": self.state}

    def pause(self):
        self.calls.append(("pause", None))
        self.state = "pause"

    def resume(self):
        self.calls.append(("resume", None))
        self.state = "play"
        self.resume_event.set()

    def play(self, query=None):
        self.calls.append(("play", query))
        self.state = "play"
        self.play_event.set()
        return (True, "", None)

    def next(self):
        self.calls.append(("next", None))
        self.next_event.set()


class FakeVolume:
    def __init__(self):
        self.calls = []

    def music_volume_up(self, amount):
        self.calls.append(("up", amount))

    def music_volume_down(self, amount):
        self.calls.append(("down", amount))

    def set_music_volume(self, volume):
        self.calls.append(("set", volume))
        return True


class FakeSpeechRecorder:
    def record_command(self):
        return b"audio"


class FakeSTT:
    def is_available(self):
        return True

    def transcribe(self, audio):
        return "continue"

    def reload(self):
        return None


class FakeIntentEngine:
    def __init__(self, intent):
        self._intent = intent

    def classify(self, text, language=None):
        return self._intent


class FakeTTS:
    def get_response_template(self, key):
        return ""

    def speak(self, text):
        return True


class FakeValidator:
    def __init__(self, intent_type):
        self.intent_type = intent_type

    def validate(self, intent):
        params = intent.parameters or {}
        return ValidationResult.valid(message="", params=params, confidence=1.0)


def _wait_for_bus_idle(bus: EventBus, timeout: float = 1.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if bus._queue.unfinished_tasks == 0:
            return
        time.sleep(0.01)
    raise AssertionError("Event bus did not drain in time")


def test_intent_continue_event_routes_to_resume_or_play():
    bus = EventBus(debug=False)
    mpd = FakeMPD(state="pause")
    volume = FakeVolume()
    PlayerEventRouter(event_bus=bus, mpd_controller=mpd, volume_manager=volume, debug=False)
    PlaybackStateMachine(event_bus=bus, mpd_controller=mpd, debug=False)

    intent = Intent(
        intent_type="continue",
        confidence=0.9,
        parameters={},
        raw_text="continue",
        language="fr",
    )
    processor = CommandProcessor(
        speech_recorder=FakeSpeechRecorder(),
        stt_engine=FakeSTT(),
        intent_engine=FakeIntentEngine(intent),
        mpd_controller=mpd,
        tts_engine=FakeTTS(),
        volume_manager=volume,
        event_bus=bus,
        command_validator=FakeValidator("continue"),
        debug=False,
        verbose=False,
    )

    bus.start()
    try:
        processor.process_command()
        _wait_for_bus_idle(bus)
        mpd.resume_event.wait(timeout=0.5)
    finally:
        bus.stop()

    assert ("resume", None) in mpd.calls


def test_set_volume_intent_routes_to_volume_manager():
    bus = EventBus(debug=False)
    mpd = FakeMPD(state="play")
    volume = FakeVolume()
    PlayerEventRouter(event_bus=bus, mpd_controller=mpd, volume_manager=volume, debug=False)
    PlaybackStateMachine(event_bus=bus, mpd_controller=mpd, debug=False)

    intent = Intent(
        intent_type="set_volume",
        confidence=0.9,
        parameters={"volume": 33},
        raw_text="mets le volume a 33",
        language="fr",
    )
    processor = CommandProcessor(
        speech_recorder=FakeSpeechRecorder(),
        stt_engine=FakeSTT(),
        intent_engine=FakeIntentEngine(intent),
        mpd_controller=mpd,
        tts_engine=FakeTTS(),
        volume_manager=volume,
        event_bus=bus,
        command_validator=FakeValidator("set_volume"),
        debug=False,
        verbose=False,
    )

    bus.start()
    try:
        processor.process_command()
        _wait_for_bus_idle(bus)
    finally:
        bus.stop()

    assert ("set", 33) in volume.calls


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
            callback(ButtonEvent(action=action, timestamp=0.0, device_name="fake"))


def test_button_events_route_to_player_actions():
    bus = EventBus(debug=False)
    mpd = FakeMPD(state="play")
    volume = FakeVolume()
    PlayerEventRouter(event_bus=bus, mpd_controller=mpd, volume_manager=volume, debug=False)
    PlaybackStateMachine(event_bus=bus, mpd_controller=mpd, debug=False)

    controller = FakeController()
    router = USBButtonRouter(controller, bus)

    bus.start()
    try:
        controller.emit(ButtonAction.SINGLE_PRESS)
        controller.emit(ButtonAction.DOUBLE_PRESS)
        mpd.next_event.wait(timeout=0.5)
    finally:
        bus.stop()
        router.stop()

    assert ("pause", None) in mpd.calls
    assert ("next", None) in mpd.calls
