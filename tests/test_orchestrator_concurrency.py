"""Concurrency: SHORT_LISTEN must not race the main process_command thread.

When the orchestrator spawns a confirmation-reply thread, a wake-word
arriving mid-listen would otherwise spawn a second process_command thread
and both would race for the mic / STT.

Spec:
  - Orchestrator's is_processing flag covers SHORT_LISTEN as well as
    process_command.
  - Wake during SHORT_LISTEN is logged + dropped, not processed.
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

import config
from modules.command_processor import CommandProcessor
from modules.command_validator import CommandValidator
from modules.control_events import (
    EVENT_CONFIRMATION_REQUESTED,
    EVENT_WAKE_WORD_DETECTED,
    new_event,
)
from modules.event_bus import EventBus
from modules.orchestrator import Orchestrator
from modules.playback_state_machine import PlaybackStateMachine


class StubMpd:
    def __init__(self, state="stop"):
        self._state = state
    def get_status(self):
        return {"state": self._state}
    def get_music_library(self):
        return None


class FakeLibrary:
    def is_empty(self):
        return False
    def search_best(self, query, exclude=None):
        return None


@pytest.fixture
def bus(monkeypatch):
    monkeypatch.setattr(config, "EVENT_BUS_ENFORCE_WHITELIST", False, raising=False)
    monkeypatch.setattr(config, "EVENT_BUS_MAX_QUEUE", 100, raising=False)
    b = EventBus(debug=False); b.start(); yield b; b.stop()


def _build_processor(bus, *, slow_stt_seconds=0.0, state_machine):
    speech_recorder = MagicMock()
    # Make record_short_reply simulate a slow listen so we can race with wake
    def slow_record(*a, **kw):
        time.sleep(slow_stt_seconds)
        return b"\x00" * 100
    speech_recorder.record_short_reply = MagicMock(side_effect=slow_record)
    speech_recorder.record_command = MagicMock(side_effect=slow_record)
    stt = MagicMock()
    stt.transcribe = MagicMock(return_value="oui")
    intent_engine = MagicMock()
    tts = MagicMock()
    tts.speak = MagicMock()
    tts.get_response_template = MagicMock(return_value=None)
    volume = MagicMock()
    validator = CommandValidator(music_library=FakeLibrary(), language="fr")
    proc = CommandProcessor(
        speech_recorder=speech_recorder, stt_engine=stt,
        intent_engine=intent_engine, mpd_controller=StubMpd("stop"),
        tts_engine=tts, volume_manager=volume, event_bus=bus,
        command_validator=validator, debug=False, verbose=False,
    )
    proc.state_machine = state_machine
    return proc


def _drain():
    time.sleep(0.05)


class TestIsProcessingCoversShortListen:
    def test_wake_during_short_listen_does_not_call_process_command(self, bus):
        """Strict version: count process_command invocations."""
        sm = PlaybackStateMachine(event_bus=bus, mpd_controller=StubMpd("stop"))
        proc = _build_processor(bus, slow_stt_seconds=0.4, state_machine=sm)
        # Track calls to process_command
        proc.process_command = MagicMock(return_value=False)

        orch = Orchestrator(command_processor=proc, event_bus=bus)
        bus.subscribe(EVENT_CONFIRMATION_REQUESTED, orch._on_confirmation_requested)
        bus.subscribe(EVENT_WAKE_WORD_DETECTED, orch._on_wake_word_detected)

        # Trigger confirmation → reply thread starts running (slow record)
        bus.publish(new_event(
            EVENT_CONFIRMATION_REQUESTED,
            {"matched_file": "X.mp3", "query": "x", "confidence": 0.55},
            source="t",
        )); _drain()
        # Mid-listen, kid says "Alexa" again
        time.sleep(0.05)  # ensure reply thread is mid-record
        bus.publish(new_event(EVENT_WAKE_WORD_DETECTED, source="t")); _drain()

        # Wait for reply to finish
        time.sleep(0.6)
        # process_command must NOT have been invoked while the reply was running
        assert proc.process_command.call_count == 0, \
            f"Wake during SHORT_LISTEN spawned a concurrent process_command "\
            f"({proc.process_command.call_count} calls)"


class TestIsProcessingReleasedAfterReply:
    def test_after_reply_finishes_wake_works_again(self, bus):
        sm = PlaybackStateMachine(event_bus=bus, mpd_controller=StubMpd("stop"))
        proc = _build_processor(bus, slow_stt_seconds=0.05, state_machine=sm)
        orch = Orchestrator(command_processor=proc, event_bus=bus)
        bus.subscribe(EVENT_CONFIRMATION_REQUESTED, orch._on_confirmation_requested)
        bus.subscribe(EVENT_WAKE_WORD_DETECTED, orch._on_wake_word_detected)

        # Reply runs and finishes quickly
        bus.publish(new_event(
            EVENT_CONFIRMATION_REQUESTED,
            {"matched_file": "X.mp3", "query": "x", "confidence": 0.55},
            source="t",
        )); _drain()
        time.sleep(0.2)
        # Reply thread done → is_processing released
        assert orch.is_processing is False
