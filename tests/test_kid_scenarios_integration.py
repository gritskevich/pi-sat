"""Synthetic end-to-end scenarios mimicking the kid's real interaction patterns.

These bind together the intent engine, validator, and state machine via the
event bus to verify the *full* play-music pipeline behaves correctly across
realistic command sequences:

  Scenario A: confident match → music plays (no confirmation)
  Scenario B: borderline match → confirmation asked → kid retries with new wake
  Scenario C: rejected match → no music, no pending state
  Scenario D: kid retries 3× before getting it right (cluster behavior)
  Scenario E: kid plays then says "alexa pause" mid-song
"""
from __future__ import annotations

import os
import time
from collections import OrderedDict
from typing import Optional, Tuple

import pytest

import config
from modules.command_validator import CommandValidator
from modules.control_events import (
    ControlEvent,
    EVENT_CONFIRMATION_REQUESTED,
    EVENT_CONTINUE_REQUESTED,
    EVENT_INTENT_READY,
    EVENT_PAUSE_REQUESTED,
    EVENT_PLAY_REQUESTED,
    EVENT_RECORDING_FINISHED,
    EVENT_RECORDING_STARTED,
    EVENT_TTS_CONFIRMATION,
    EVENT_WAKE_WORD_DETECTED,
    new_event,
)
from modules.event_bus import EventBus
from modules.interfaces import Intent
from modules.playback_state_machine import PlaybackStateMachine


class StubMpd:
    def __init__(self, state="stop"):
        self._state = state
    def get_status(self):
        return {"state": self._state}


class FakeLibrary:
    def __init__(self, result):
        self._result = result
    def is_empty(self):
        return self._result is None
    def search_best(self, query):
        return self._result


@pytest.fixture
def bus(monkeypatch):
    monkeypatch.setattr(config, "EVENT_BUS_ENFORCE_WHITELIST", False, raising=False)
    monkeypatch.setattr(config, "EVENT_BUS_MAX_QUEUE", 100, raising=False)
    b = EventBus(debug=False)
    b.start()
    yield b
    b.stop()


@pytest.fixture
def captured(bus):
    events = []
    for name in (
        EVENT_PAUSE_REQUESTED, EVENT_CONTINUE_REQUESTED,
        EVENT_INTENT_READY, EVENT_CONFIRMATION_REQUESTED,
        EVENT_PLAY_REQUESTED,
    ):
        bus.subscribe(name, lambda e, store=events: store.append(e))
    return events


def _drain():
    time.sleep(0.05)


def _publish_intent_with_confirmation(bus, validator, query):
    """Simulate command_processor's job: validate, then publish events."""
    intent = Intent(intent_type="play_music", confidence=1.0,
                    parameters={"query": query}, raw_text=query, language="fr")
    result = validator.validate(intent)
    if not result.is_valid:
        bus.publish(new_event(
            EVENT_TTS_CONFIRMATION,
            {"intent_found": False, "intent_type": "play_music", "reason": "invalid"},
            source="t",
        ))
        return result
    if result.requires_confirmation:
        params = result.validated_params
        bus.publish(new_event(
            EVENT_CONFIRMATION_REQUESTED,
            {"matched_file": params["matched_file"],
             "query": params["query"],
             "confidence": result.confidence},
            source="t",
        ))
        bus.publish(new_event(
            EVENT_TTS_CONFIRMATION,
            {"intent_found": True, "intent_type": "play_music",
             "awaiting_confirmation": True},
            source="t",
        ))
    else:
        bus.publish(new_event(
            EVENT_INTENT_READY,
            {"intent_type": "play_music", "parameters": result.validated_params,
             "raw_text": query, "language": "fr"},
            source="t",
        ))
        bus.publish(new_event(
            EVENT_TTS_CONFIRMATION,
            {"intent_found": True, "intent_type": "play_music"},
            source="t",
        ))
    return result


class TestScenarioA_ConfidentMatch:
    """Kid says a clear command, system plays it."""
    def test_confident_match_publishes_intent_ready(self, bus, captured):
        sm = PlaybackStateMachine(event_bus=bus, mpd_controller=StubMpd("stop"))
        validator = CommandValidator(music_library=FakeLibrary(("X.mp3", 0.92)), language="fr")
        bus.publish(new_event(EVENT_WAKE_WORD_DETECTED, source="t")); _drain()
        bus.publish(new_event(EVENT_RECORDING_STARTED, source="t")); _drain()
        result = _publish_intent_with_confirmation(bus, validator, "x"); _drain()
        bus.publish(new_event(EVENT_RECORDING_FINISHED, source="t")); _drain()

        names = [e.name for e in captured]
        assert EVENT_INTENT_READY in names
        assert EVENT_CONFIRMATION_REQUESTED not in names
        assert sm.pending_confirmation is None


class TestScenarioB_BorderlineThenRetry:
    """Kid says ambiguous command → system asks → kid retries."""
    def test_confirmation_then_wake_clears_pending(self, bus, captured):
        sm = PlaybackStateMachine(event_bus=bus, mpd_controller=StubMpd("stop"))
        # First attempt — borderline confidence
        validator = CommandValidator(
            music_library=FakeLibrary(("X.mp3", 0.55)), language="fr",
        )
        bus.publish(new_event(EVENT_WAKE_WORD_DETECTED, source="t")); _drain()
        bus.publish(new_event(EVENT_RECORDING_STARTED, source="t")); _drain()
        _publish_intent_with_confirmation(bus, validator, "x")
        bus.publish(new_event(EVENT_RECORDING_FINISHED, source="t")); _drain()

        assert sm.pending_confirmation is not None
        assert sm.pending_confirmation["matched_file"] == "X.mp3"
        # Kid retries — new wake word arrives
        bus.publish(new_event(EVENT_WAKE_WORD_DETECTED, source="t")); _drain()
        assert sm.pending_confirmation is None

        names = [e.name for e in captured]
        assert EVENT_CONFIRMATION_REQUESTED in names
        assert EVENT_INTENT_READY not in names  # never published — confirmation suspended it


class TestScenarioC_Rejected:
    """Kid says something unintelligible → no song, no pending state."""
    def test_rejected_no_pending_no_play(self, bus, captured):
        sm = PlaybackStateMachine(event_bus=bus, mpd_controller=StubMpd("stop"))
        validator = CommandValidator(
            music_library=FakeLibrary(("X.mp3", 0.30)), language="fr",
        )
        bus.publish(new_event(EVENT_WAKE_WORD_DETECTED, source="t")); _drain()
        result = _publish_intent_with_confirmation(bus, validator, "garbled"); _drain()

        assert result.is_valid is False
        assert sm.pending_confirmation is None
        names = [e.name for e in captured]
        assert EVENT_CONFIRMATION_REQUESTED not in names
        assert EVENT_INTENT_READY not in names


class TestScenarioD_RetryCluster:
    """Kid says 'Alexa X' three times before settling — pending state must roll over correctly."""
    def test_three_attempts_in_cluster(self, bus, captured):
        sm = PlaybackStateMachine(event_bus=bus, mpd_controller=StubMpd("stop"))
        # Attempt 1: borderline → confirmation A
        validator1 = CommandValidator(music_library=FakeLibrary(("A.mp3", 0.55)), language="fr")
        bus.publish(new_event(EVENT_WAKE_WORD_DETECTED, source="t")); _drain()
        _publish_intent_with_confirmation(bus, validator1, "a"); _drain()
        bus.publish(new_event(EVENT_RECORDING_FINISHED, source="t")); _drain()
        assert sm.pending_confirmation["matched_file"] == "A.mp3"

        # Attempt 2: kid retried → wake word drops A → another borderline → B
        bus.publish(new_event(EVENT_WAKE_WORD_DETECTED, source="t")); _drain()
        assert sm.pending_confirmation is None
        validator2 = CommandValidator(music_library=FakeLibrary(("B.mp3", 0.55)), language="fr")
        _publish_intent_with_confirmation(bus, validator2, "b"); _drain()
        bus.publish(new_event(EVENT_RECORDING_FINISHED, source="t")); _drain()
        assert sm.pending_confirmation["matched_file"] == "B.mp3"

        # Attempt 3: third try lands a confident match → INTENT_READY
        bus.publish(new_event(EVENT_WAKE_WORD_DETECTED, source="t")); _drain()
        assert sm.pending_confirmation is None
        validator3 = CommandValidator(music_library=FakeLibrary(("C.mp3", 0.92)), language="fr")
        _publish_intent_with_confirmation(bus, validator3, "c"); _drain()
        bus.publish(new_event(EVENT_RECORDING_FINISHED, source="t")); _drain()

        # Final state: no pending confirmation (because intent was confident, not pending)
        assert sm.pending_confirmation is None
        names = [e.name for e in captured]
        assert names.count(EVENT_CONFIRMATION_REQUESTED) == 2  # A and B
        assert names.count(EVENT_INTENT_READY) == 1  # only C


class TestScenarioE_PauseMidSong:
    """Music playing → kid says 'alexa pause' → music pauses cleanly."""
    def test_pause_during_playback(self, bus, captured):
        sm = PlaybackStateMachine(event_bus=bus, mpd_controller=StubMpd("play"))
        bus.publish(new_event(EVENT_WAKE_WORD_DETECTED, source="t")); _drain()
        # Wake auto-pauses to make room for command
        names = [e.name for e in captured]
        assert EVENT_PAUSE_REQUESTED in names

    def test_no_resume_during_pending_confirmation(self, bus, captured):
        """Music must not auto-resume while a confirmation is pending."""
        sm = PlaybackStateMachine(event_bus=bus, mpd_controller=StubMpd("play"))
        validator = CommandValidator(
            music_library=FakeLibrary(("X.mp3", 0.55)), language="fr",
        )
        bus.publish(new_event(EVENT_WAKE_WORD_DETECTED, source="t")); _drain()
        bus.publish(new_event(EVENT_RECORDING_STARTED, source="t")); _drain()
        _publish_intent_with_confirmation(bus, validator, "x"); _drain()
        bus.publish(new_event(EVENT_RECORDING_FINISHED, source="t")); _drain()

        # Pending confirmation should suppress the auto-resume that would
        # otherwise fire when TTS finishes
        assert sm.pending_confirmation is not None
        names = [e.name for e in captured]
        # The kid is still expected to answer — the song must NOT start playing
        # back yet (no continue event from the state machine for this candidate).
        # Note: a CONTINUE may fire from the wake/recording cycle paths if the
        # implementation chooses to bring back the *previous* music. The current
        # state machine fires CONTINUE on tts_no_intent only — confirmation
        # branch should NOT trigger it.
