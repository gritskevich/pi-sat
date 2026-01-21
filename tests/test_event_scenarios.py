import random
import time

import config
from modules.control_events import (
    ControlEvent,
    EVENT_BUTTON_PRESSED,
    EVENT_BUTTON_DOUBLE_PRESSED,
    EVENT_VOLUME_UP_REQUESTED,
    EVENT_VOLUME_DOWN_REQUESTED,
    EVENT_PAUSE_REQUESTED,
    EVENT_CONTINUE_REQUESTED,
    EVENT_NEXT_TRACK_REQUESTED,
    EVENT_PREV_TRACK_REQUESTED,
    EVENT_SET_VOLUME_REQUESTED,
    EVENT_PLAY_REQUESTED,
    EVENT_PLAY_FAVORITES_REQUESTED,
    EVENT_ADD_FAVORITE_REQUESTED,
    EVENT_SLEEP_TIMER_REQUESTED,
    EVENT_REPEAT_MODE_REQUESTED,
    EVENT_SHUFFLE_REQUESTED,
    EVENT_QUEUE_ADD_REQUESTED,
    EVENT_MUSIC_SEARCH_REQUESTED,
    EVENT_MUSIC_RESOLVED,
    EVENT_INTENT_DETECTED,
    EVENT_INTENT_READY,
    EVENT_RECORDING_STARTED,
    EVENT_RECORDING_FINISHED,
    EVENT_TTS_CONFIRMATION,
    EVENT_WAKE_WORD_DETECTED,
)
from modules.event_bus import EventBus
from modules.music_search_router import MusicSearchRouter
from modules.player_event_router import PlayerEventRouter
from modules.playback_state_machine import PlaybackStateMachine


class FakeLibrary:
    def search_best(self, query):
        return ("maman.mp3", 0.9)


class FakeMPD:
    def __init__(self, state="stop"):
        self.calls = []
        self.state = state
        self._library = FakeLibrary()

    def get_music_library(self):
        return self._library

    def get_status(self):
        return {"state": self.state}

    def play(self, query=None):
        self.calls.append(("play", query))
        self.state = "play"
        return (True, "", None)

    def pause(self):
        self.calls.append(("pause", None))
        self.state = "pause"
        return (True, "")

    def resume(self):
        self.calls.append(("resume", None))
        self.state = "play"
        return (True, "")

    def next(self):
        self.calls.append(("next", None))
        return (True, "")

    def previous(self):
        self.calls.append(("previous", None))
        return (True, "")

    def play_favorites(self):
        self.calls.append(("play_favorites", None))
        self.state = "play"
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
    def __init__(self, initial=20, max_volume=None):
        self.calls = []
        self.max_volume = int(max_volume if max_volume is not None else getattr(config, "MAX_VOLUME", 100))
        self.volume = int(initial)

    def music_volume_up(self, amount):
        self.volume = min(self.max_volume, self.volume + int(amount))
        self.calls.append(("up", amount, self.volume))

    def music_volume_down(self, amount):
        self.volume = max(0, self.volume - int(amount))
        self.calls.append(("down", amount, self.volume))

    def set_music_volume(self, volume):
        self.volume = min(self.max_volume, max(0, int(volume)))
        self.calls.append(("set", self.volume))
        return True


def _wait_for_bus_idle(bus: EventBus, timeout: float = 1.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if bus._queue.unfinished_tasks == 0:
            return
        time.sleep(0.01)
    raise AssertionError("Event bus did not drain in time")


def _make_event(name: str, payload=None, source="test"):
    return ControlEvent.now(name, payload or {}, source=source)


def _event_payload(name: str, rng: random.Random):
    if name == EVENT_SET_VOLUME_REQUESTED:
        return {"volume": rng.randint(0, 100)}
    if name == EVENT_PLAY_REQUESTED:
        return {"query": "maman", "matched_file": "maman.mp3"}
    if name == EVENT_SLEEP_TIMER_REQUESTED:
        return {"duration_minutes": rng.choice([5, 10, 30])}
    if name == EVENT_REPEAT_MODE_REQUESTED:
        return {"mode": rng.choice(["on", "off"])}
    if name == EVENT_SHUFFLE_REQUESTED:
        return {"enabled": rng.choice([True, False])}
    if name == EVENT_QUEUE_ADD_REQUESTED:
        return {"query": "maman", "play_next": rng.choice([True, False])}
    if name == EVENT_MUSIC_SEARCH_REQUESTED:
        return {"query": "maman", "language": "fr", "raw_text": "joue maman"}
    if name == EVENT_WAKE_WORD_DETECTED:
        return {"wake_word": "alexa_v0.1", "confidence": 0.9}
    if name == EVENT_INTENT_READY:
        return {
            "intent_type": "play_music",
            "parameters": {"query": "maman", "matched_file": "maman.mp3"},
            "raw_text": "joue maman",
            "language": "fr",
        }
    if name == EVENT_TTS_CONFIRMATION:
        return {"intent_found": True, "intent_type": "play_music"}
    if name == EVENT_INTENT_DETECTED:
        return {"intent_type": "play_music", "confidence": 0.9}
    if name == EVENT_MUSIC_RESOLVED:
        return {"query": "maman", "matched_file": "maman.mp3", "confidence": 0.9}
    return {}


def _build_system(initial_state="stop", initial_volume=20):
    bus = EventBus(debug=False)
    mpd = FakeMPD(state=initial_state)
    volume = FakeVolume(initial=initial_volume)

    PlayerEventRouter(event_bus=bus, mpd_controller=mpd, volume_manager=volume, debug=False)
    MusicSearchRouter(event_bus=bus, music_library=mpd.get_music_library(), debug=False)
    PlaybackStateMachine(event_bus=bus, mpd_controller=mpd, debug=False)

    return bus, mpd, volume


def _run_sequence(bus, sequence):
    for event in sequence:
        bus.publish(event)
        _wait_for_bus_idle(bus)


def test_fixed_event_scenarios():
    scenarios = [
        {
            "name": "wake_word_then_button",
            "initial_state": "play",
            "events": [EVENT_WAKE_WORD_DETECTED, EVENT_BUTTON_PRESSED],
            "expect_state": "pause",
            "expect_calls": [("pause", None)],
        },
        {
            "name": "wake_word_while_paused_no_double_pause",
            "initial_state": "pause",
            "events": [EVENT_WAKE_WORD_DETECTED],
            "expect_state": "pause",
            "expect_calls": [],
        },
        {
            "name": "button_then_wake_word",
            "initial_state": "play",
            "events": [EVENT_BUTTON_PRESSED, EVENT_WAKE_WORD_DETECTED],
            "expect_state": "pause",
            "expect_calls": [("pause", None)],
        },
        {
            "name": "button_ignored_during_recording",
            "initial_state": "play",
            "events": [EVENT_RECORDING_STARTED, EVENT_BUTTON_PRESSED, EVENT_RECORDING_FINISHED],
            "expect_state": "pause",
            "expect_calls": [("pause", None)],
        },
        {
            "name": "startup_continue_no_resume",
            "initial_state": "stop",
            "events": [EVENT_CONTINUE_REQUESTED],
            "expect_state": "play",
            "expect_calls": [("play", None)],
        },
        {
            "name": "no_intent_resumes_after_tts",
            "initial_state": "play",
            "events": [EVENT_WAKE_WORD_DETECTED, EVENT_RECORDING_STARTED, EVENT_RECORDING_FINISHED, EVENT_TTS_CONFIRMATION],
            "expect_state": "play",
            "expect_calls": [("pause", None), ("resume", None)],
            "payloads": {
                EVENT_TTS_CONFIRMATION: {"intent_found": False, "reason": "no_intent"},
            },
        },
        {
            "name": "tts_before_intent_no_action",
            "initial_state": "play",
            "events": [EVENT_TTS_CONFIRMATION],
            "expect_state": "play",
            "expect_calls": [],
            "payloads": {
                EVENT_TTS_CONFIRMATION: {"intent_found": True, "intent_type": "play_music"},
            },
        },
        {
            "name": "recording_blocks_resume",
            "initial_state": "play",
            "events": [EVENT_RECORDING_STARTED, EVENT_PAUSE_REQUESTED, EVENT_RECORDING_FINISHED],
            "expect_state": "pause",
            "expect_calls": [("pause", None)],
        },
        {
            "name": "recording_blocks_double_press",
            "initial_state": "play",
            "events": [EVENT_RECORDING_STARTED, EVENT_BUTTON_DOUBLE_PRESSED, EVENT_RECORDING_FINISHED],
            "expect_state": "pause",
            "expect_calls": [("pause", None)],
        },
        {
            "name": "intent_play_after_tts",
            "initial_state": "pause",
            "events": [EVENT_INTENT_READY, EVENT_TTS_CONFIRMATION],
            "expect_state": "play",
            "expect_calls": [("play", "maman.mp3")],
        },
        {
            "name": "intent_ready_without_tts_no_change",
            "initial_state": "play",
            "events": [EVENT_INTENT_READY],
            "expect_state": "play",
            "expect_calls": [],
        },
        {
            "name": "intent_pause_after_tts",
            "initial_state": "play",
            "events": [EVENT_INTENT_READY, EVENT_TTS_CONFIRMATION],
            "expect_state": "pause",
            "expect_calls": [("pause", None)],
            "payloads": {
                EVENT_INTENT_READY: {
                    "intent_type": "pause",
                    "parameters": {},
                    "raw_text": "pause",
                    "language": "fr",
                },
                EVENT_TTS_CONFIRMATION: {"intent_found": True, "intent_type": "pause"},
            },
        },
        {
            "name": "intent_set_volume_after_tts",
            "initial_state": "play",
            "events": [EVENT_INTENT_READY, EVENT_TTS_CONFIRMATION],
            "expect_state": "play",
            "expect_calls": [],
            "payloads": {
                EVENT_INTENT_READY: {
                    "intent_type": "set_volume",
                    "parameters": {"volume": 33},
                    "raw_text": "volume 33",
                    "language": "fr",
                },
                EVENT_TTS_CONFIRMATION: {"intent_found": True, "intent_type": "set_volume"},
            },
        },
        {
            "name": "intent_queue_add_after_tts",
            "initial_state": "play",
            "events": [EVENT_INTENT_READY, EVENT_TTS_CONFIRMATION],
            "expect_state": "play",
            "expect_calls": [],
            "payloads": {
                EVENT_INTENT_READY: {
                    "intent_type": "queue_add",
                    "parameters": {"query": "maman", "play_next": True},
                    "raw_text": "ajoute maman",
                    "language": "fr",
                },
                EVENT_TTS_CONFIRMATION: {"intent_found": True, "intent_type": "queue_add"},
            },
        },
        {
            "name": "double_press_next",
            "initial_state": "play",
            "events": [EVENT_BUTTON_DOUBLE_PRESSED],
            "expect_state": "play",
            "expect_calls": [("next", None)],
        },
        {
            "name": "multiple_wake_words_during_interaction",
            "initial_state": "play",
            "events": [EVENT_WAKE_WORD_DETECTED, EVENT_RECORDING_STARTED, EVENT_WAKE_WORD_DETECTED],
            "expect_state": "pause",
            "expect_calls": [("pause", None)],
        },
        {
            "name": "set_volume_ignored_during_recording",
            "initial_state": "play",
            "events": [EVENT_RECORDING_STARTED, EVENT_INTENT_READY, EVENT_TTS_CONFIRMATION],
            "expect_state": "pause",
            "expect_calls": [("pause", None)],
            "payloads": {
                EVENT_INTENT_READY: {
                    "intent_type": "set_volume",
                    "parameters": {"volume": 25},
                    "raw_text": "volume 25",
                    "language": "fr",
                },
                EVENT_TTS_CONFIRMATION: {"intent_found": True, "intent_type": "set_volume"},
            },
        },
        {
            "name": "volume_up_while_playing_stays_playing",
            "initial_state": "play",
            "events": [EVENT_VOLUME_UP_REQUESTED],
            "expect_state": "play",
            "expect_calls": [],
        },
        {
            "name": "volume_down_while_playing_stays_playing",
            "initial_state": "play",
            "events": [EVENT_VOLUME_DOWN_REQUESTED],
            "expect_state": "play",
            "expect_calls": [],
        },
        {
            "name": "play_then_volume_up_stays_playing",
            "initial_state": "stop",
            "events": [EVENT_PLAY_REQUESTED, EVENT_VOLUME_UP_REQUESTED],
            "expect_state": "play",
            "expect_calls": [("play", "maman.mp3")],
        },
        {
            "name": "play_then_volume_down_stays_playing",
            "initial_state": "stop",
            "events": [EVENT_PLAY_REQUESTED, EVENT_VOLUME_DOWN_REQUESTED],
            "expect_state": "play",
            "expect_calls": [("play", "maman.mp3")],
        },
        {
            "name": "voice_volume_up_resumes_after",
            "initial_state": "play",
            "events": [EVENT_WAKE_WORD_DETECTED, EVENT_RECORDING_STARTED, EVENT_INTENT_READY, EVENT_TTS_CONFIRMATION, EVENT_RECORDING_FINISHED],
            "expect_state": "play",
            "expect_calls": [("pause", None), ("resume", None)],
            "payloads": {
                EVENT_INTENT_READY: {
                    "intent_type": "volume_up",
                    "parameters": {},
                    "raw_text": "plus fort",
                    "language": "fr",
                },
                EVENT_TTS_CONFIRMATION: {"intent_found": True, "intent_type": "volume_up"},
            },
        },
        {
            "name": "voice_volume_down_resumes_after",
            "initial_state": "play",
            "events": [EVENT_WAKE_WORD_DETECTED, EVENT_RECORDING_STARTED, EVENT_INTENT_READY, EVENT_TTS_CONFIRMATION, EVENT_RECORDING_FINISHED],
            "expect_state": "play",
            "expect_calls": [("pause", None), ("resume", None)],
            "payloads": {
                EVENT_INTENT_READY: {
                    "intent_type": "volume_down",
                    "parameters": {},
                    "raw_text": "moins fort",
                    "language": "fr",
                },
                EVENT_TTS_CONFIRMATION: {"intent_found": True, "intent_type": "volume_down"},
            },
        },
        {
            "name": "voice_set_volume_resumes_after",
            "initial_state": "play",
            "events": [EVENT_WAKE_WORD_DETECTED, EVENT_RECORDING_STARTED, EVENT_INTENT_READY, EVENT_TTS_CONFIRMATION, EVENT_RECORDING_FINISHED],
            "expect_state": "play",
            "expect_calls": [("pause", None), ("resume", None)],
            "payloads": {
                EVENT_INTENT_READY: {
                    "intent_type": "set_volume",
                    "parameters": {"volume": 50},
                    "raw_text": "volume 50",
                    "language": "fr",
                },
                EVENT_TTS_CONFIRMATION: {"intent_found": True, "intent_type": "set_volume"},
            },
        },
    ]

    for scenario in scenarios:
        bus, mpd, volume = _build_system(
            initial_state=scenario["initial_state"],
            initial_volume=20,
        )
        bus.start()
        try:
            rng = random.Random(0)
            payloads = scenario.get("payloads", {})
            seq = [
                _make_event(
                    name,
                    payloads.get(name, _event_payload(name, rng)),
                )
                for name in scenario["events"]
            ]
            _run_sequence(bus, seq)
        finally:
            bus.stop()

        assert mpd.state == scenario["expect_state"]
        for expected in scenario["expect_calls"]:
            assert expected in mpd.calls
        assert volume.volume <= getattr(config, "MAX_VOLUME", 100)


def test_random_event_sequences_invariants():
    rng = random.Random(42)
    all_events = [
        EVENT_BUTTON_PRESSED,
        EVENT_BUTTON_DOUBLE_PRESSED,
        EVENT_VOLUME_UP_REQUESTED,
        EVENT_VOLUME_DOWN_REQUESTED,
        EVENT_PAUSE_REQUESTED,
        EVENT_CONTINUE_REQUESTED,
        EVENT_NEXT_TRACK_REQUESTED,
        EVENT_PREV_TRACK_REQUESTED,
        EVENT_SET_VOLUME_REQUESTED,
        EVENT_PLAY_REQUESTED,
        EVENT_PLAY_FAVORITES_REQUESTED,
        EVENT_ADD_FAVORITE_REQUESTED,
        EVENT_SLEEP_TIMER_REQUESTED,
        EVENT_REPEAT_MODE_REQUESTED,
        EVENT_SHUFFLE_REQUESTED,
        EVENT_QUEUE_ADD_REQUESTED,
        EVENT_MUSIC_SEARCH_REQUESTED,
        EVENT_MUSIC_RESOLVED,
        EVENT_INTENT_DETECTED,
        EVENT_INTENT_READY,
        EVENT_RECORDING_STARTED,
        EVENT_RECORDING_FINISHED,
        EVENT_TTS_CONFIRMATION,
        EVENT_WAKE_WORD_DETECTED,
    ]

    sequences = []
    for event_name in all_events:
        sequences.append([event_name])
    for _ in range(40):
        length = rng.randint(4, 10)
        sequences.append([rng.choice(all_events) for _ in range(length)])

    for sequence in sequences:
        bus, mpd, volume = _build_system(initial_state=rng.choice(["stop", "pause", "play"]))
        bus.start()
        recording_active = False
        try:
            for event_name in sequence:
                payload = _event_payload(event_name, rng)
                bus.publish(_make_event(event_name, payload))
                _wait_for_bus_idle(bus)

                if event_name == EVENT_RECORDING_STARTED:
                    recording_active = True
                if event_name == EVENT_RECORDING_FINISHED:
                    recording_active = False

                if recording_active:
                    assert mpd.state != "play"
                if event_name == EVENT_TTS_CONFIRMATION:
                    if not payload.get("intent_found", False):
                        assert ("play", "maman.mp3") not in mpd.calls
                assert volume.volume <= getattr(config, "MAX_VOLUME", 100)
        finally:
            bus.stop()
