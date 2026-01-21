import time
from modules.command_processor import CommandProcessor
from modules.event_bus import EventBus
from modules.player_event_router import PlayerEventRouter
from modules.playback_state_machine import PlaybackStateMachine
from modules.intent_engine import IntentEngine


class FakeLibrary:
    def search_best(self, query):
        return ("maman.mp3", 0.9)


class FakeMPD:
    def __init__(self, state="play"):
        self.state = state
        self.calls = []
        self._library = FakeLibrary()

    def get_music_library(self):
        return self._library

    def get_status(self):
        return {"state": self.state}

    def pause(self):
        self.calls.append(("pause", None))
        self.state = "pause"
        return (True, "")

    def resume(self):
        self.calls.append(("resume", None))
        self.state = "play"
        return (True, "")

    def play(self, query=None):
        self.calls.append(("play", query))
        self.state = "play"
        return (True, "", None)

    def next(self):
        self.calls.append(("next", None))
        return (True, "")

    def previous(self):
        self.calls.append(("previous", None))
        return (True, "")

    def play_favorites(self):
        self.calls.append(("play_favorites", None))
        return (True, "")

    def add_to_favorites(self):
        self.calls.append(("add_favorites", None))
        return (True, "")

    def set_sleep_timer(self, minutes):
        self.calls.append(("sleep_timer", minutes))
        return (True, "")

    def set_repeat(self, mode):
        self.calls.append(("repeat", mode))
        return (True, "")

    def set_shuffle(self, enabled):
        self.calls.append(("shuffle", enabled))
        return (True, "")

    def add_to_queue(self, query, play_next=False):
        self.calls.append(("queue", query, play_next))
        return (True, "")


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
    def __init__(self, text):
        self._text = text

    def is_available(self):
        return True

    def transcribe(self, audio):
        return self._text

    def reload(self):
        return None


class FakeTTS:
    def get_response_template(self, key):
        return ""

    def speak(self, text):
        return True


def _wait_for_bus_idle(bus: EventBus, timeout: float = 1.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if bus._queue.unfinished_tasks == 0:
            return
        time.sleep(0.01)
    raise AssertionError("Event bus did not drain in time")


def _build_pipeline(stt_text: str, mpd_state: str = "play"):
    bus = EventBus(debug=False)
    mpd = FakeMPD(state=mpd_state)
    volume = FakeVolume()

    PlayerEventRouter(event_bus=bus, mpd_controller=mpd, volume_manager=volume, debug=False)
    PlaybackStateMachine(event_bus=bus, mpd_controller=mpd, debug=False)

    processor = CommandProcessor(
        speech_recorder=FakeSpeechRecorder(),
        stt_engine=FakeSTT(stt_text),
        intent_engine=IntentEngine(language="fr"),
        mpd_controller=mpd,
        tts_engine=FakeTTS(),
        volume_manager=volume,
        event_bus=bus,
        debug=False,
        verbose=False,
    )

    return bus, mpd, volume, processor


def test_e2e_pause_intent_does_not_resume():
    bus, mpd, volume, processor = _build_pipeline("arrete la musique", mpd_state="play")

    bus.start()
    try:
        processor.process_command()
        _wait_for_bus_idle(bus)
    finally:
        bus.stop()

    assert ("resume", None) not in mpd.calls
    assert ("pause", None) in mpd.calls


def test_e2e_continue_intent_plays_when_stopped():
    bus, mpd, volume, processor = _build_pipeline("continue la musique", mpd_state="stop")

    bus.start()
    try:
        processor.process_command()
        _wait_for_bus_idle(bus)
    finally:
        bus.stop()

    assert ("play", None) in mpd.calls


def test_e2e_volume_up_down_intents():
    bus, mpd, volume, processor = _build_pipeline("plus fort", mpd_state="play")

    bus.start()
    try:
        processor.process_command()
        _wait_for_bus_idle(bus)
    finally:
        bus.stop()

    assert any(call[0] == "up" for call in volume.calls)
