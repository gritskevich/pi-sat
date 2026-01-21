import threading
import time

from modules.command_processor import CommandProcessor
from modules.command_validator import ValidationResult
from modules.control_events import ControlEvent, EVENT_RECORDING_STARTED, EVENT_RECORDING_FINISHED
from modules.event_bus import EventBus
from modules.music_search_router import MusicSearchRouter
from modules.player_event_router import PlayerEventRouter
from modules.playback_state_machine import PlaybackStateMachine
from modules.interfaces import Intent


class FakeLibrary:
    def search_best(self, query):
        return ("maman.mp3", 0.9)


class FakeMPD:
    def __init__(self):
        self.calls = []
        self.state = "play"
        self._library = FakeLibrary()
        self.play_event = threading.Event()
        self.pause_event = threading.Event()
        self.resume_event = threading.Event()

    def get_music_library(self):
        return self._library

    def get_status(self):
        return {"state": self.state}

    def play(self, query=None):
        self.calls.append(("play", query))
        self.state = "play"
        self.play_event.set()
        return (True, "", None)

    def pause(self):
        self.calls.append(("pause", None))
        self.state = "pause"
        self.pause_event.set()
        return (True, "")

    def resume(self):
        self.calls.append(("resume", None))
        self.state = "play"
        self.resume_event.set()
        return (True, "")

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
    def is_available(self):
        return True

    def transcribe(self, audio):
        return "joue maman"

    def reload(self):
        return None


class FakeIntentEngine:
    def classify(self, text, language=None):
        return Intent(
            intent_type="play_music",
            confidence=0.9,
            parameters={"query": "maman"},
            raw_text=text,
            language="fr",
        )


class FakeTTS:
    def get_response_template(self, key):
        return ""

    def speak(self, text):
        return True


class FakeValidator:
    def validate(self, intent):
        return ValidationResult.valid(
            message="",
            params={"query": "maman"},
            confidence=0.9,
        )


def test_command_processor_event_flow_triggers_play_and_state_machine():
    bus = EventBus(debug=False)
    mpd = FakeMPD()
    volume = FakeVolume()

    PlayerEventRouter(event_bus=bus, mpd_controller=mpd, volume_manager=volume, debug=False)
    MusicSearchRouter(event_bus=bus, music_library=mpd.get_music_library(), debug=False)
    PlaybackStateMachine(event_bus=bus, mpd_controller=mpd, debug=False)

    processor = CommandProcessor(
        speech_recorder=FakeSpeechRecorder(),
        stt_engine=FakeSTT(),
        intent_engine=FakeIntentEngine(),
        mpd_controller=mpd,
        tts_engine=FakeTTS(),
        volume_manager=volume,
        event_bus=bus,
        command_validator=FakeValidator(),
        debug=False,
        verbose=False,
    )

    bus.start()
    try:
        processor.process_command()
        mpd.play_event.wait(timeout=0.5)
        mpd.pause_event.wait(timeout=0.5)
        deadline = time.time() + 1.0
        while time.time() < deadline and bus._queue.unfinished_tasks:
            time.sleep(0.01)
    finally:
        bus.stop()

    assert ("play", "maman.mp3") in mpd.calls
    assert ("pause", None) in mpd.calls
