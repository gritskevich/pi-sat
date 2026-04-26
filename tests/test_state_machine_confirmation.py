"""Tests for the confirmation lane in PlaybackStateMachine.

When `EVENT_CONFIRMATION_REQUESTED` arrives:
  - the state machine remembers the pending candidate (file, query)
  - it does NOT publish play/pause events on its own
  - it stays in the "awaiting confirmation" lane until either:
    * a new wake word arrives (kid retried) — drop the pending candidate
    * a TTS-confirmation event arrives without `awaiting_confirmation` flag
    * a manual reset (timeout, future)

For now the state machine just tracks the pending state; the actual listen-
for-response flow is Phase 2. These tests pin the contract so Phase 2 has
something concrete to plug into.
"""
from __future__ import annotations

import pytest

import config
from modules.control_events import (
    ControlEvent,
    EVENT_CONFIRMATION_REQUESTED,
    EVENT_WAKE_WORD_DETECTED,
    new_event,
)
from modules.event_bus import EventBus
from modules.playback_state_machine import PlaybackStateMachine


@pytest.fixture
def bus(monkeypatch):
    monkeypatch.setattr(config, "EVENT_BUS_ENFORCE_WHITELIST", False, raising=False)
    monkeypatch.setattr(config, "EVENT_BUS_MAX_QUEUE", 100, raising=False)
    b = EventBus(debug=False)
    b.start()
    yield b
    b.stop()


@pytest.fixture
def sm(bus):
    # No mpd controller — state machine should still track pending state
    return PlaybackStateMachine(event_bus=bus, mpd_controller=None, debug=False)


def _publish_and_drain(bus, event):
    bus.publish(event)
    # EventBus is async — give it a beat to dispatch
    import time
    time.sleep(0.05)


class TestConfirmationLane:
    def test_confirmation_request_sets_pending_candidate(self, bus, sm):
        _publish_and_drain(bus, new_event(
            EVENT_CONFIRMATION_REQUESTED,
            {"matched_file": "X.mp3", "query": "x", "confidence": 0.55},
            source="test",
        ))
        assert sm.pending_confirmation is not None
        assert sm.pending_confirmation["matched_file"] == "X.mp3"
        assert sm.pending_confirmation["query"] == "x"

    def test_wake_word_clears_pending_confirmation(self, bus, sm):
        _publish_and_drain(bus, new_event(
            EVENT_CONFIRMATION_REQUESTED,
            {"matched_file": "X.mp3", "query": "x", "confidence": 0.55},
            source="test",
        ))
        assert sm.pending_confirmation is not None

        # Kid retried with a new "Alexa" — the previous candidate is stale
        _publish_and_drain(bus, new_event(
            EVENT_WAKE_WORD_DETECTED, {"wake_word": "alexa"}, source="test",
        ))
        assert sm.pending_confirmation is None

    def test_idle_state_machine_has_no_pending(self, sm):
        assert sm.pending_confirmation is None

    def test_second_confirmation_overwrites_first(self, bus, sm):
        _publish_and_drain(bus, new_event(
            EVENT_CONFIRMATION_REQUESTED,
            {"matched_file": "A.mp3", "query": "a", "confidence": 0.55},
            source="test",
        ))
        _publish_and_drain(bus, new_event(
            EVENT_CONFIRMATION_REQUESTED,
            {"matched_file": "B.mp3", "query": "b", "confidence": 0.55},
            source="test",
        ))
        assert sm.pending_confirmation["matched_file"] == "B.mp3"
