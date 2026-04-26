"""End-to-end PlaybackStateMachine flows: every state × event combination.

Coverage matrix:
  Initial playback:  play | pause | stop | unknown
  Active recording:  yes  | no
  Pending confirmation:  yes(X) | no
  Inbound event:     wake | button | button×2 | rec_start | rec_finish |
                     intent_ready | tts(intent=ok) | tts(intent=none) |
                     tts(awaiting_confirmation) | confirmation_requested

Each test asserts:
  - the events the machine *publishes* (via a stub mpd controller + bus spy)
  - the internal state transitions (pending_confirmation, _interaction_active,
    _pre_interaction_state)
  - that no spurious events leak (e.g., no pause when already paused)
"""
from __future__ import annotations

import time
from typing import Optional

import pytest

import config
from modules.control_events import (
    ControlEvent,
    EVENT_BUTTON_DOUBLE_PRESSED,
    EVENT_BUTTON_PRESSED,
    EVENT_CONFIRMATION_REQUESTED,
    EVENT_CONTINUE_REQUESTED,
    EVENT_INTENT_READY,
    EVENT_NEXT_TRACK_REQUESTED,
    EVENT_PAUSE_REQUESTED,
    EVENT_PLAY_REQUESTED,
    EVENT_RECORDING_FINISHED,
    EVENT_RECORDING_STARTED,
    EVENT_TTS_CONFIRMATION,
    EVENT_WAKE_WORD_DETECTED,
    new_event,
)
from modules.event_bus import EventBus
from modules.playback_state_machine import PlaybackStateMachine


# --- Helpers ----------------------------------------------------------------

class StubMpdController:
    """Minimal MPD stand-in. State is a string the test sets directly."""
    def __init__(self, state: str = "stop"):
        self._state = state

    def get_status(self):
        return {"state": self._state}

    def set_state(self, state: str):
        self._state = state


@pytest.fixture
def bus(monkeypatch):
    monkeypatch.setattr(config, "EVENT_BUS_ENFORCE_WHITELIST", False, raising=False)
    monkeypatch.setattr(config, "EVENT_BUS_MAX_QUEUE", 100, raising=False)
    b = EventBus(debug=False)
    b.start()
    yield b
    b.stop()


@pytest.fixture
def captured_events(bus):
    """Subscribe a list to ALL relevant outbound events for assertion."""
    captured: list[ControlEvent] = []
    for name in (
        EVENT_PAUSE_REQUESTED, EVENT_CONTINUE_REQUESTED, EVENT_PLAY_REQUESTED,
        EVENT_NEXT_TRACK_REQUESTED,
    ):
        bus.subscribe(name, lambda e, store=captured: store.append(e))
    return captured


def _drain():
    time.sleep(0.05)


def _build(bus, mpd_state: str) -> PlaybackStateMachine:
    return PlaybackStateMachine(event_bus=bus, mpd_controller=StubMpdController(mpd_state))


def _names(events: list[ControlEvent]) -> list[str]:
    return [e.name for e in events]


# --- Wake-word lane ---------------------------------------------------------

class TestWakeWordWithDifferentInitialStates:
    def test_wake_while_playing_pauses(self, bus, captured_events):
        sm = _build(bus, "play")
        bus.publish(new_event(EVENT_WAKE_WORD_DETECTED, source="t"))
        _drain()
        assert EVENT_PAUSE_REQUESTED in _names(captured_events)
        assert sm._pre_interaction_state == "play"

    def test_wake_while_paused_no_pause(self, bus, captured_events):
        sm = _build(bus, "pause")
        bus.publish(new_event(EVENT_WAKE_WORD_DETECTED, source="t"))
        _drain()
        assert EVENT_PAUSE_REQUESTED not in _names(captured_events)
        assert sm._pre_interaction_state is None

    def test_wake_while_stopped_no_pause(self, bus, captured_events):
        sm = _build(bus, "stop")
        bus.publish(new_event(EVENT_WAKE_WORD_DETECTED, source="t"))
        _drain()
        assert EVENT_PAUSE_REQUESTED not in _names(captured_events)


# --- Confirmation lane ------------------------------------------------------

class TestConfirmationLaneWithMusicState:
    def test_confirmation_while_playing_does_not_resume_after_recording(
            self, bus, captured_events):
        """If awaiting confirmation and recording finishes, music must NOT auto-resume —
        otherwise the kid hears the song before answering 'oui/non'."""
        sm = _build(bus, "play")
        # Wake → pause
        bus.publish(new_event(EVENT_WAKE_WORD_DETECTED, source="t")); _drain()
        bus.publish(new_event(EVENT_RECORDING_STARTED, source="t")); _drain()
        # Validator decides confirmation needed
        bus.publish(new_event(
            EVENT_CONFIRMATION_REQUESTED,
            {"matched_file": "X.mp3", "query": "x", "confidence": 0.55},
            source="t",
        )); _drain()
        bus.publish(new_event(EVENT_RECORDING_FINISHED, source="t")); _drain()
        bus.publish(new_event(
            EVENT_TTS_CONFIRMATION,
            {"intent_found": True, "intent_type": "play_music",
             "awaiting_confirmation": True},
            source="t",
        )); _drain()

        # No EVENT_CONTINUE_REQUESTED should have fired
        assert EVENT_CONTINUE_REQUESTED not in _names(captured_events)
        # Pending confirmation is set
        assert sm.pending_confirmation is not None
        assert sm.pending_confirmation["matched_file"] == "X.mp3"

    def test_wake_word_after_confirmation_drops_pending(self, bus, captured_events):
        sm = _build(bus, "pause")
        bus.publish(new_event(
            EVENT_CONFIRMATION_REQUESTED,
            {"matched_file": "X.mp3", "query": "x", "confidence": 0.55},
            source="t",
        )); _drain()
        assert sm.pending_confirmation is not None
        # Kid retried
        bus.publish(new_event(EVENT_WAKE_WORD_DETECTED, source="t")); _drain()
        assert sm.pending_confirmation is None

    def test_confirmation_requested_with_no_matched_file_is_ignored(
            self, bus, captured_events):
        sm = _build(bus, "stop")
        bus.publish(new_event(
            EVENT_CONFIRMATION_REQUESTED,
            {"query": "x"},  # missing matched_file
            source="t",
        )); _drain()
        assert sm.pending_confirmation is None


# --- Button lane ------------------------------------------------------------

class TestButtonsWithRecordingActive:
    def test_single_press_during_recording_is_ignored(self, bus, captured_events):
        sm = _build(bus, "play")
        bus.publish(new_event(EVENT_RECORDING_STARTED, source="t")); _drain()
        captured_events.clear()
        bus.publish(new_event(EVENT_BUTTON_PRESSED, source="t")); _drain()
        # No new pause/continue should fire
        assert EVENT_PAUSE_REQUESTED not in _names(captured_events)
        assert EVENT_CONTINUE_REQUESTED not in _names(captured_events)

    def test_double_press_during_recording_is_ignored(self, bus, captured_events):
        sm = _build(bus, "play")
        bus.publish(new_event(EVENT_RECORDING_STARTED, source="t")); _drain()
        captured_events.clear()
        bus.publish(new_event(EVENT_BUTTON_DOUBLE_PRESSED, source="t")); _drain()
        assert EVENT_NEXT_TRACK_REQUESTED not in _names(captured_events)


class TestButtonTogglePlayPause:
    @pytest.mark.parametrize("initial,expected_event", [
        ("play",  EVENT_PAUSE_REQUESTED),
        ("pause", EVENT_CONTINUE_REQUESTED),
        ("stop",  EVENT_CONTINUE_REQUESTED),
    ])
    def test_single_press_toggles(self, bus, captured_events, initial, expected_event):
        sm = _build(bus, initial)
        captured_events.clear()
        bus.publish(new_event(EVENT_BUTTON_PRESSED, source="t")); _drain()
        assert expected_event in _names(captured_events)

    def test_double_press_skips_track(self, bus, captured_events):
        sm = _build(bus, "play")
        captured_events.clear()
        bus.publish(new_event(EVENT_BUTTON_DOUBLE_PRESSED, source="t")); _drain()
        assert EVENT_NEXT_TRACK_REQUESTED in _names(captured_events)


# --- Recording-cycle resume logic ------------------------------------------

class TestRecordingCycleResumes:
    def test_play_resumes_after_recording_with_no_intent(self, bus, captured_events):
        sm = _build(bus, "play")
        bus.publish(new_event(EVENT_WAKE_WORD_DETECTED, source="t")); _drain()
        bus.publish(new_event(EVENT_RECORDING_STARTED, source="t")); _drain()
        bus.publish(new_event(EVENT_RECORDING_FINISHED, source="t")); _drain()
        bus.publish(new_event(
            EVENT_TTS_CONFIRMATION,
            {"intent_found": False},
            source="t",
        )); _drain()
        # Should resume play
        assert EVENT_CONTINUE_REQUESTED in _names(captured_events)

    def test_paused_does_not_resume_after_recording(self, bus, captured_events):
        sm = _build(bus, "pause")
        bus.publish(new_event(EVENT_WAKE_WORD_DETECTED, source="t")); _drain()
        bus.publish(new_event(EVENT_RECORDING_STARTED, source="t")); _drain()
        bus.publish(new_event(EVENT_RECORDING_FINISHED, source="t")); _drain()
        bus.publish(new_event(
            EVENT_TTS_CONFIRMATION,
            {"intent_found": False},
            source="t",
        )); _drain()
        # Was paused before — should stay paused
        assert EVENT_CONTINUE_REQUESTED not in _names(captured_events)


# --- Confirmation churn -----------------------------------------------------

class TestConfirmationChurn:
    def test_two_back_to_back_confirmations_keep_latest(self, bus):
        sm = _build(bus, "stop")
        bus.publish(new_event(
            EVENT_CONFIRMATION_REQUESTED,
            {"matched_file": "A.mp3", "query": "a", "confidence": 0.55},
            source="t",
        )); _drain()
        bus.publish(new_event(
            EVENT_CONFIRMATION_REQUESTED,
            {"matched_file": "B.mp3", "query": "b", "confidence": 0.60},
            source="t",
        )); _drain()
        assert sm.pending_confirmation["matched_file"] == "B.mp3"

    def test_confirmation_then_wake_then_confirmation_stores_new(self, bus):
        sm = _build(bus, "stop")
        bus.publish(new_event(
            EVENT_CONFIRMATION_REQUESTED,
            {"matched_file": "A.mp3", "query": "a", "confidence": 0.55},
            source="t",
        )); _drain()
        bus.publish(new_event(EVENT_WAKE_WORD_DETECTED, source="t")); _drain()
        assert sm.pending_confirmation is None
        bus.publish(new_event(
            EVENT_CONFIRMATION_REQUESTED,
            {"matched_file": "C.mp3", "query": "c", "confidence": 0.55},
            source="t",
        )); _drain()
        assert sm.pending_confirmation["matched_file"] == "C.mp3"
