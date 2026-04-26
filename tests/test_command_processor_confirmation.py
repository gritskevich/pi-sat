"""Tests for CommandProcessor.process_confirmation_reply (Phase 3 wiring).

Captures the kid's reply during the SHORT_LISTEN window, parses it, and
publishes the corresponding domain event:
    AFFIRM → EVENT_CONFIRMATION_AFFIRMED
    DENY   → EVENT_CONFIRMATION_DENIED + TTS "Dis-moi encore" + loop back
    TIMEOUT/UNINTELLIGIBLE → EVENT_CONFIRMATION_TIMEOUT
    NEW_COMMAND → re-run validation pipeline with current exclusion set
"""
from __future__ import annotations

import time
from typing import Optional
from unittest.mock import MagicMock

import pytest

import config
from modules.command_processor import CommandProcessor
from modules.command_validator import CommandValidator
from modules.control_events import (
    EVENT_CONFIRMATION_AFFIRMED,
    EVENT_CONFIRMATION_DENIED,
    EVENT_CONFIRMATION_REQUESTED,
    EVENT_CONFIRMATION_TIMEOUT,
    EVENT_INTENT_READY,
    new_event,
)
from modules.event_bus import EventBus
from modules.playback_state_machine import PlaybackStateMachine


class StubMpd:
    def __init__(self, state="stop"):
        self._state = state
    def get_status(self):
        return {"state": self._state}
    def get_music_library(self):
        return None


class FakeLibrary:
    def __init__(self, results=None):
        self._results = list(results or [])
        self.last_exclude = None
    def is_empty(self):
        return False
    def search_best(self, query, exclude=None):
        self.last_exclude = set(exclude or [])
        if not self._results:
            return None
        return self._results.pop(0)


@pytest.fixture
def bus(monkeypatch):
    monkeypatch.setattr(config, "EVENT_BUS_ENFORCE_WHITELIST", False, raising=False)
    monkeypatch.setattr(config, "EVENT_BUS_MAX_QUEUE", 100, raising=False)
    b = EventBus(debug=False); b.start(); yield b; b.stop()


def _build_processor(bus, *, stt_returns="oui", state_machine=None,
                     mpd=None, library=None):
    mpd = mpd or StubMpd("stop")
    library = library or FakeLibrary()
    speech_recorder = MagicMock()
    speech_recorder.record_command = MagicMock(return_value=b"\x00" * 100)
    speech_recorder.record_short_reply = MagicMock(return_value=b"\x00" * 100)
    stt = MagicMock()
    stt.transcribe = MagicMock(return_value=stt_returns)
    intent_engine = MagicMock()
    tts = MagicMock()
    tts.speak = MagicMock()
    tts.get_response_template = MagicMock(return_value="error")
    volume = MagicMock()
    validator = CommandValidator(music_library=library, language="fr")
    proc = CommandProcessor(
        speech_recorder=speech_recorder,
        stt_engine=stt,
        intent_engine=intent_engine,
        mpd_controller=mpd,
        tts_engine=tts,
        volume_manager=volume,
        event_bus=bus,
        command_validator=validator,
        debug=False,
        verbose=False,
    )
    if state_machine is not None:
        proc.state_machine = state_machine
    return proc, tts, speech_recorder, stt


def _drain():
    time.sleep(0.05)


# --- Reply class → event mapping ------------------------------------------

class TestReplyToEventMapping:
    def test_affirm_publishes_affirmed_with_pending(self, bus):
        sm = PlaybackStateMachine(event_bus=bus, mpd_controller=StubMpd("stop"))
        bus.publish(new_event(
            EVENT_CONFIRMATION_REQUESTED,
            {"matched_file": "X.mp3", "query": "x", "confidence": 0.55},
            source="t",
        )); _drain()
        proc, tts, recorder, stt = _build_processor(bus, stt_returns="oui",
                                                     state_machine=sm)

        captured = []
        bus.subscribe(EVENT_CONFIRMATION_AFFIRMED,
                      lambda e: captured.append(e))

        proc.process_confirmation_reply(); _drain()

        assert len(captured) == 1
        assert captured[0].payload.get("matched_file") == "X.mp3"

    def test_deny_publishes_denied_and_speaks_redo(self, bus):
        sm = PlaybackStateMachine(event_bus=bus, mpd_controller=StubMpd("stop"))
        bus.publish(new_event(
            EVENT_CONFIRMATION_REQUESTED,
            {"matched_file": "X.mp3", "query": "x", "confidence": 0.55},
            source="t",
        )); _drain()
        proc, tts, recorder, stt = _build_processor(bus, stt_returns="non",
                                                     state_machine=sm)

        captured = []
        bus.subscribe(EVENT_CONFIRMATION_DENIED,
                      lambda e: captured.append(e))

        proc.process_confirmation_reply(); _drain()

        assert len(captured) == 1
        assert captured[0].payload.get("matched_file") == "X.mp3"
        # TTS spoke a "say it again" prompt
        speak_calls = [c.args[0] for c in tts.speak.call_args_list]
        assert any(("encore" in s.lower() or "dis-moi" in s.lower() or "redis" in s.lower())
                   for s in speak_calls), \
            f"Expected 'try again' prompt in TTS, got: {speak_calls}"

    def test_timeout_publishes_timeout(self, bus):
        sm = PlaybackStateMachine(event_bus=bus, mpd_controller=StubMpd("stop"))
        bus.publish(new_event(
            EVENT_CONFIRMATION_REQUESTED,
            {"matched_file": "X.mp3", "query": "x", "confidence": 0.55},
            source="t",
        )); _drain()
        # STT returns empty → TIMEOUT
        proc, tts, recorder, stt = _build_processor(bus, stt_returns="",
                                                     state_machine=sm)

        captured = []
        bus.subscribe(EVENT_CONFIRMATION_TIMEOUT,
                      lambda e: captured.append(e))

        proc.process_confirmation_reply(); _drain()

        assert len(captured) == 1

    def test_unintelligible_publishes_timeout(self, bus):
        sm = PlaybackStateMachine(event_bus=bus, mpd_controller=StubMpd("stop"))
        bus.publish(new_event(
            EVENT_CONFIRMATION_REQUESTED,
            {"matched_file": "X.mp3", "query": "x", "confidence": 0.55},
            source="t",
        )); _drain()
        proc, tts, recorder, stt = _build_processor(bus,
                                                     stt_returns="ouais nan attends",
                                                     state_machine=sm)
        captured = []
        bus.subscribe(EVENT_CONFIRMATION_TIMEOUT,
                      lambda e: captured.append(e))
        proc.process_confirmation_reply(); _drain()
        # Ambiguous → routed to TIMEOUT (don't risk false DENY)
        assert len(captured) == 1


# --- Loop-back wiring -------------------------------------------------------

class TestDenyLoopBack:
    def test_deny_does_not_keep_pending_after_publish(self, bus):
        """After DENY, pending_confirmation must be cleared (state machine handles it)."""
        sm = PlaybackStateMachine(event_bus=bus, mpd_controller=StubMpd("stop"))
        bus.publish(new_event(
            EVENT_CONFIRMATION_REQUESTED,
            {"matched_file": "X.mp3", "query": "x", "confidence": 0.55},
            source="t",
        )); _drain()
        proc, *_ = _build_processor(bus, stt_returns="non", state_machine=sm)
        proc.process_confirmation_reply(); _drain()
        assert sm.pending_confirmation is None
        assert "X.mp3" in sm.excluded_files


# --- Edge cases -------------------------------------------------------------

class TestEdgeCases:
    def test_no_pending_no_publish(self, bus):
        """If no pending confirmation, process_confirmation_reply is a no-op."""
        sm = PlaybackStateMachine(event_bus=bus, mpd_controller=StubMpd("stop"))
        # No EVENT_CONFIRMATION_REQUESTED first
        proc, *_ = _build_processor(bus, stt_returns="oui", state_machine=sm)

        captured = []
        for n in (EVENT_CONFIRMATION_AFFIRMED, EVENT_CONFIRMATION_DENIED,
                  EVENT_CONFIRMATION_TIMEOUT):
            bus.subscribe(n, lambda e, store=captured: store.append(e))

        proc.process_confirmation_reply(); _drain()
        assert captured == []

    def test_no_audio_returns_timeout(self, bus):
        sm = PlaybackStateMachine(event_bus=bus, mpd_controller=StubMpd("stop"))
        bus.publish(new_event(
            EVENT_CONFIRMATION_REQUESTED,
            {"matched_file": "X.mp3", "query": "x", "confidence": 0.55},
            source="t",
        )); _drain()
        proc, *_ = _build_processor(bus, state_machine=sm)
        # speech_recorder returns no audio
        proc.speech_recorder.record_short_reply = MagicMock(return_value=None)

        captured = []
        bus.subscribe(EVENT_CONFIRMATION_TIMEOUT,
                      lambda e: captured.append(e))

        proc.process_confirmation_reply(); _drain()
        assert len(captured) == 1
