"""End-to-end synthetic kid scenarios for the full confirmation+DENY loop.

These bind validator + state machine + reply parser via the event bus to
verify the *full* loop semantics under realistic command sequences.
"""
from __future__ import annotations

import time
from typing import Optional

import pytest

import config
from modules.command_validator import CommandValidator
from modules.control_events import (
    ControlEvent,
    EVENT_CONFIRMATION_AFFIRMED,
    EVENT_CONFIRMATION_DENIED,
    EVENT_CONFIRMATION_GIVE_UP,
    EVENT_CONFIRMATION_REQUESTED,
    EVENT_CONFIRMATION_TIMEOUT,
    EVENT_CONTINUE_REQUESTED,
    EVENT_INTENT_READY,
    EVENT_PAUSE_REQUESTED,
    EVENT_RECORDING_FINISHED,
    EVENT_RECORDING_STARTED,
    EVENT_TTS_CONFIRMATION,
    EVENT_WAKE_WORD_DETECTED,
    new_event,
)
from modules.event_bus import EventBus
from modules.interfaces import Intent
from modules.playback_state_machine import PlaybackStateMachine
from modules.reply_parser import AFFIRM, DENY, NEW_COMMAND, parse_reply


class StubMpd:
    def __init__(self, state="stop"):
        self._state = state
    def get_status(self):
        return {"state": self._state}


class FakeLibrary:
    """Returns a queue of search results — first call → first result, etc."""
    def __init__(self, results):
        self._results = list(results)
        self.last_query = None
        self.last_exclude = None

    def is_empty(self):
        return not self._results

    def search_best(self, query, exclude=None):
        self.last_query = query
        self.last_exclude = set(exclude or [])
        if not self._results:
            return None
        return self._results.pop(0)


@pytest.fixture
def bus(monkeypatch):
    monkeypatch.setattr(config, "EVENT_BUS_ENFORCE_WHITELIST", False, raising=False)
    monkeypatch.setattr(config, "EVENT_BUS_MAX_QUEUE", 100, raising=False)
    b = EventBus(debug=False); b.start(); yield b; b.stop()


def _drain():
    time.sleep(0.05)


def _names(events):
    return [e.name for e in events]


def _publish_validation(bus, validator, query):
    intent = Intent(intent_type="play_music", confidence=1.0,
                    parameters={"query": query}, raw_text=query, language="fr")
    result = validator.validate(intent)
    if not result.is_valid:
        return result
    if result.requires_confirmation:
        bus.publish(new_event(
            EVENT_CONFIRMATION_REQUESTED,
            {"matched_file": result.validated_params["matched_file"],
             "query": result.validated_params["query"],
             "confidence": result.confidence},
            source="t",
        ))
    else:
        bus.publish(new_event(
            EVENT_INTENT_READY,
            {"intent_type": "play_music", "parameters": result.validated_params,
             "raw_text": query, "language": "fr"},
            source="t",
        ))
    return result


def _kid_replies(bus, sm, text: str):
    """Simulate the SHORT_LISTEN → reply parser path."""
    reply = parse_reply(text)
    pending = sm.pending_confirmation or {}
    if reply.cls is AFFIRM:
        bus.publish(new_event(EVENT_CONFIRMATION_AFFIRMED,
                              {"matched_file": pending.get("matched_file"),
                               "query": pending.get("query")},
                              source="reply_parser"))
    elif reply.cls is DENY:
        bus.publish(new_event(EVENT_CONFIRMATION_DENIED,
                              {"matched_file": pending.get("matched_file"),
                               "query": pending.get("query")},
                              source="reply_parser"))
    return reply


# --- SCENARIO 1 -------------------------------------------------------------

class TestScenario_ConfidentMatch_OneShot:
    """Kid says clear command, system plays — no confirmation needed."""

    def test(self, bus):
        captured = []
        for n in (EVENT_INTENT_READY, EVENT_CONFIRMATION_REQUESTED):
            bus.subscribe(n, lambda e, store=captured: store.append(e))
        sm = PlaybackStateMachine(event_bus=bus, mpd_controller=StubMpd("stop"))
        validator = CommandValidator(
            music_library=FakeLibrary([("X.mp3", 0.92)]), language="fr",
        )
        bus.publish(new_event(EVENT_WAKE_WORD_DETECTED, source="t")); _drain()
        _publish_validation(bus, validator, "x"); _drain()
        names = _names(captured)
        assert EVENT_INTENT_READY in names
        assert EVENT_CONFIRMATION_REQUESTED not in names


# --- SCENARIO 2 -------------------------------------------------------------

class TestScenario_DenyThenCorrectMatch:
    """Borderline match → kid says non → exclusion → next match → affirm → play."""

    def test(self, bus):
        captured = []
        for n in (EVENT_INTENT_READY, EVENT_CONFIRMATION_REQUESTED,
                  EVENT_CONFIRMATION_AFFIRMED, EVENT_CONFIRMATION_DENIED):
            bus.subscribe(n, lambda e, store=captured: store.append(e))
        sm = PlaybackStateMachine(event_bus=bus, mpd_controller=StubMpd("stop"))
        # Library returns A first, then B (after exclusion of A)
        library = FakeLibrary([("A.mp3", 0.55), ("B.mp3", 0.92)])
        validator = CommandValidator(music_library=library, language="fr")

        bus.publish(new_event(EVENT_WAKE_WORD_DETECTED, source="t")); _drain()
        _publish_validation(bus, validator, "x"); _drain()
        assert sm.pending_confirmation["matched_file"] == "A.mp3"

        # Kid says "non"
        _kid_replies(bus, sm, "non"); _drain()
        assert "A.mp3" in sm.excluded_files
        assert sm.pending_confirmation is None  # cleared after DENY

        # Loop back: kid speaks again, validator runs with exclusion
        # In real flow this happens via a SHORT_LISTEN follow-up; here we
        # simulate by calling validate again. Validator must receive the
        # exclusion set so search_best filters correctly.
        intent = Intent(intent_type="play_music", confidence=1.0,
                        parameters={"query": "x"}, raw_text="x", language="fr")
        # The library will be called with exclude={"A.mp3"} via the validator
        result = validator.validate(intent, exclude=sm.excluded_files)
        assert result.is_valid
        assert result.validated_params["matched_file"] == "B.mp3"
        assert library.last_exclude == {"A.mp3"}


# --- SCENARIO 3 -------------------------------------------------------------

class TestScenario_ThreeDenysGiveUp:
    """3 denies in a row → give-up → music resumes if it was playing."""

    def test(self, bus):
        give_up_events = []
        continue_events = []
        bus.subscribe(EVENT_CONFIRMATION_GIVE_UP,
                      lambda e: give_up_events.append(e))
        bus.subscribe(EVENT_CONTINUE_REQUESTED,
                      lambda e: continue_events.append(e))
        sm = PlaybackStateMachine(event_bus=bus, mpd_controller=StubMpd("play"))
        bus.publish(new_event(EVENT_WAKE_WORD_DETECTED, source="t")); _drain()
        for fp in ("A.mp3", "B.mp3", "C.mp3"):
            bus.publish(new_event(EVENT_CONFIRMATION_REQUESTED,
                                  {"matched_file": fp, "query": "x", "confidence": 0.55},
                                  source="t")); _drain()
            bus.publish(new_event(EVENT_CONFIRMATION_DENIED,
                                  {"matched_file": fp}, source="t")); _drain()
        assert len(give_up_events) == 1
        assert len(continue_events) == 1  # music resumes on give-up
        assert sm.excluded_files == set()  # reset


# --- SCENARIO 4 -------------------------------------------------------------

class TestScenario_DenyThenWakeRestartsFresh:
    """DENY then a fresh wake = reset everything."""

    def test(self, bus):
        sm = PlaybackStateMachine(event_bus=bus, mpd_controller=StubMpd("stop"))
        bus.publish(new_event(EVENT_CONFIRMATION_REQUESTED,
                              {"matched_file": "X.mp3", "query": "x", "confidence": 0.55},
                              source="t")); _drain()
        bus.publish(new_event(EVENT_CONFIRMATION_DENIED,
                              {"matched_file": "X.mp3"}, source="t")); _drain()
        assert "X.mp3" in sm.excluded_files
        bus.publish(new_event(EVENT_WAKE_WORD_DETECTED, source="t")); _drain()
        assert sm.excluded_files == set()
        assert sm.consecutive_denies == 0


# --- SCENARIO 5 -------------------------------------------------------------

class TestScenario_AffirmAfterDeny:
    """DENY followed by a different match's AFFIRM resets denies counter too."""

    def test(self, bus):
        sm = PlaybackStateMachine(event_bus=bus, mpd_controller=StubMpd("stop"))
        bus.publish(new_event(EVENT_CONFIRMATION_REQUESTED,
                              {"matched_file": "A.mp3", "query": "x", "confidence": 0.55},
                              source="t")); _drain()
        bus.publish(new_event(EVENT_CONFIRMATION_DENIED,
                              {"matched_file": "A.mp3"}, source="t")); _drain()
        assert sm.consecutive_denies == 1
        bus.publish(new_event(EVENT_CONFIRMATION_REQUESTED,
                              {"matched_file": "B.mp3", "query": "x", "confidence": 0.55},
                              source="t")); _drain()
        bus.publish(new_event(EVENT_CONFIRMATION_AFFIRMED,
                              {"matched_file": "B.mp3"}, source="t")); _drain()
        assert sm.excluded_files == set()
        assert sm.consecutive_denies == 0


# --- SCENARIO 6 -------------------------------------------------------------

class TestScenario_TimeoutPreservesExclusionsResumesMusic:
    """Kid stays silent → timeout → music back, exclusions kept (cluster lives)."""

    def test(self, bus):
        captured = []
        for n in (EVENT_CONTINUE_REQUESTED,):
            bus.subscribe(n, lambda e, store=captured: store.append(e))
        sm = PlaybackStateMachine(event_bus=bus, mpd_controller=StubMpd("play"))
        bus.publish(new_event(EVENT_WAKE_WORD_DETECTED, source="t")); _drain()
        bus.publish(new_event(EVENT_CONFIRMATION_REQUESTED,
                              {"matched_file": "X.mp3", "query": "x", "confidence": 0.55},
                              source="t")); _drain()
        bus.publish(new_event(EVENT_CONFIRMATION_DENIED,
                              {"matched_file": "X.mp3"}, source="t")); _drain()
        assert "X.mp3" in sm.excluded_files
        bus.publish(new_event(EVENT_CONFIRMATION_TIMEOUT, source="t")); _drain()
        # Resumes music
        assert len(captured) == 1
        # But keeps exclusions
        assert "X.mp3" in sm.excluded_files


# --- SCENARIO 7 -------------------------------------------------------------

class TestScenario_NewCommandInsideLoop:
    """Kid says 'mets autre chose' instead of yes/no → restart pipeline fresh."""

    def test_parser_classifies_as_new_command(self):
        reply = parse_reply("mets autre chose")
        assert reply.cls is NEW_COMMAND


# --- SCENARIO 8 -------------------------------------------------------------

class TestScenario_AllSongsExcludedFallsBackToRejected:
    """If exclusion empties the candidate pool, validator returns invalid (Rejected)."""

    def test(self, bus):
        # Library has only one song
        library = FakeLibrary([("A.mp3", 0.55), None])  # second call returns None
        validator = CommandValidator(music_library=library, language="fr")
        intent = Intent(intent_type="play_music", confidence=1.0,
                        parameters={"query": "x"}, raw_text="x", language="fr")
        # First call works
        r1 = validator.validate(intent)
        assert r1.is_valid
        # Second call with exclusion of the only song → Rejected
        r2 = validator.validate(intent, exclude={"A.mp3"})
        assert r2.is_valid is False
