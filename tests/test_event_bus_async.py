import threading
import time

from modules.control_events import ControlEvent, EVENT_WAKE_WORD_DETECTED
from modules.event_bus import EventBus
from modules.orchestrator import Orchestrator
from modules.playback_state_machine import PlaybackStateMachine
from modules.player_event_router import PlayerEventRouter


class _FakeMPD:
    def __init__(self, state="play"):
        self.state = state
        self.calls = []
        self.pause_event = threading.Event()

    def get_status(self):
        return {"state": self.state}

    def pause(self):
        self.calls.append(("pause", None))
        self.state = "pause"
        self.pause_event.set()

    def resume(self):
        self.calls.append(("resume", None))
        self.state = "play"

    def play(self, query=None):
        self.calls.append(("play", query))
        self.state = "play"

    def next(self):
        self.calls.append(("next", None))

    def previous(self):
        self.calls.append(("previous", None))

    def play_favorites(self):
        self.calls.append(("play_favorites", None))

    def add_to_favorites(self):
        self.calls.append(("add_favorites", None))

    def set_sleep_timer(self, minutes):
        self.calls.append(("sleep_timer", minutes))

    def set_repeat(self, mode):
        self.calls.append(("repeat", mode))

    def set_shuffle(self, enabled):
        self.calls.append(("shuffle", enabled))

    def add_to_queue(self, query, play_next=False):
        self.calls.append(("queue", query, play_next))


class _FakeVolume:
    def music_volume_up(self, amount):
        return None

    def music_volume_down(self, amount):
        return None

    def set_music_volume(self, volume):
        return True


class _BlockingCommandProcessor:
    def __init__(self):
        self.started = threading.Event()
        self.release = threading.Event()

    def process_command(self):
        self.started.set()
        self.release.wait(timeout=2.0)
        return True


def _build_system(mpd_state="play"):
    bus = EventBus(debug=False)
    mpd = _FakeMPD(state=mpd_state)
    volume = _FakeVolume()
    PlayerEventRouter(event_bus=bus, mpd_controller=mpd, volume_manager=volume, debug=False)
    PlaybackStateMachine(event_bus=bus, mpd_controller=mpd, debug=False)
    return bus, mpd


def test_wake_word_pause_not_blocked_by_command_processing():
    bus, mpd = _build_system(mpd_state="play")
    processor = _BlockingCommandProcessor()
    orchestrator = Orchestrator(
        command_processor=processor,
        wake_word_listener=None,
        event_bus=bus,
        verbose=False,
        debug=False,
    )
    bus.subscribe(EVENT_WAKE_WORD_DETECTED, orchestrator._on_wake_word_detected)

    bus.start()
    try:
        bus.publish(ControlEvent.now(EVENT_WAKE_WORD_DETECTED, source="test"))
        assert processor.started.wait(timeout=0.5)
        assert mpd.pause_event.wait(timeout=0.5)
        assert ("pause", None) in mpd.calls
        processor.release.set()
    finally:
        bus.stop()


def test_wake_word_when_paused_does_not_pause_again():
    bus, mpd = _build_system(mpd_state="pause")
    processor = _BlockingCommandProcessor()
    orchestrator = Orchestrator(
        command_processor=processor,
        wake_word_listener=None,
        event_bus=bus,
        verbose=False,
        debug=False,
    )
    bus.subscribe(EVENT_WAKE_WORD_DETECTED, orchestrator._on_wake_word_detected)

    bus.start()
    try:
        bus.publish(ControlEvent.now(EVENT_WAKE_WORD_DETECTED, source="test"))
        assert processor.started.wait(timeout=0.5)
        assert not mpd.pause_event.wait(timeout=0.2)
        assert ("pause", None) not in mpd.calls
        processor.release.set()
    finally:
        bus.stop()


def test_wake_word_ignored_when_processing():
    bus, _ = _build_system(mpd_state="play")
    processor = _BlockingCommandProcessor()
    orchestrator = Orchestrator(
        command_processor=processor,
        wake_word_listener=None,
        event_bus=bus,
        verbose=False,
        debug=False,
    )
    bus.subscribe(EVENT_WAKE_WORD_DETECTED, orchestrator._on_wake_word_detected)

    bus.start()
    try:
        orchestrator.is_processing = True
        bus.publish(ControlEvent.now(EVENT_WAKE_WORD_DETECTED, source="test"))
        time.sleep(0.1)
        assert not processor.started.is_set()
    finally:
        bus.stop()
