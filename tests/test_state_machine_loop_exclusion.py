"""State machine: DENY loop with exclusion set + anti-alias telemetry.

The state machine maintains:
  excluded_files: set[str]  — songs the kid has rejected this cluster
  consecutive_denies: int   — for the 3-strike give-up rule

Lifecycle:
  - new wake word        → reset excl, denies := 0
  - DENY                 → add pending file to excl, denies += 1
  - 3rd consecutive DENY → reset, give-up
  - AFFIRM               → reset
  - TIMEOUT              → keep excl (kid may retry within cluster)
"""
from __future__ import annotations

import time

import pytest

import config
from modules.control_events import (
    ControlEvent,
    EVENT_CONFIRMATION_AFFIRMED,
    EVENT_CONFIRMATION_DENIED,
    EVENT_CONFIRMATION_REQUESTED,
    EVENT_CONFIRMATION_TIMEOUT,
    EVENT_CONFIRMATION_GIVE_UP,
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
    return PlaybackStateMachine(event_bus=bus, mpd_controller=None, debug=False)


def _drain():
    time.sleep(0.05)


def _request_confirmation(bus, file: str, query: str = "x", conf: float = 0.55):
    bus.publish(new_event(
        EVENT_CONFIRMATION_REQUESTED,
        {"matched_file": file, "query": query, "confidence": conf},
        source="t",
    ))


class TestExclusionLifecycle:
    def test_initial_excluded_is_empty(self, sm):
        assert sm.excluded_files == set()
        assert sm.consecutive_denies == 0

    def test_deny_adds_pending_to_excluded(self, bus, sm):
        _request_confirmation(bus, "X.mp3"); _drain()
        bus.publish(new_event(EVENT_CONFIRMATION_DENIED,
                              {"matched_file": "X.mp3"}, source="t")); _drain()
        assert "X.mp3" in sm.excluded_files
        assert sm.consecutive_denies == 1

    def test_two_denies_accumulate_exclusions(self, bus, sm):
        _request_confirmation(bus, "X.mp3"); _drain()
        bus.publish(new_event(EVENT_CONFIRMATION_DENIED,
                              {"matched_file": "X.mp3"}, source="t")); _drain()
        _request_confirmation(bus, "Y.mp3"); _drain()
        bus.publish(new_event(EVENT_CONFIRMATION_DENIED,
                              {"matched_file": "Y.mp3"}, source="t")); _drain()
        assert sm.excluded_files == {"X.mp3", "Y.mp3"}
        assert sm.consecutive_denies == 2

    def test_third_deny_triggers_give_up_and_resets(self, bus, sm):
        give_up_events = []
        bus.subscribe(EVENT_CONFIRMATION_GIVE_UP,
                      lambda e: give_up_events.append(e))
        # 3 denies in a row
        for fp in ("A.mp3", "B.mp3", "C.mp3"):
            _request_confirmation(bus, fp); _drain()
            bus.publish(new_event(EVENT_CONFIRMATION_DENIED,
                                  {"matched_file": fp}, source="t")); _drain()
        # 3rd DENY publishes give-up + resets
        assert len(give_up_events) == 1
        assert sm.excluded_files == set()
        assert sm.consecutive_denies == 0

    def test_affirm_resets_exclusion(self, bus, sm):
        _request_confirmation(bus, "X.mp3"); _drain()
        bus.publish(new_event(EVENT_CONFIRMATION_DENIED,
                              {"matched_file": "X.mp3"}, source="t")); _drain()
        _request_confirmation(bus, "Y.mp3"); _drain()
        bus.publish(new_event(EVENT_CONFIRMATION_AFFIRMED,
                              {"matched_file": "Y.mp3"}, source="t")); _drain()
        assert sm.excluded_files == set()
        assert sm.consecutive_denies == 0

    def test_wake_word_resets_exclusion(self, bus, sm):
        _request_confirmation(bus, "X.mp3"); _drain()
        bus.publish(new_event(EVENT_CONFIRMATION_DENIED,
                              {"matched_file": "X.mp3"}, source="t")); _drain()
        assert "X.mp3" in sm.excluded_files
        bus.publish(new_event(EVENT_WAKE_WORD_DETECTED, source="t")); _drain()
        assert sm.excluded_files == set()
        assert sm.consecutive_denies == 0


class TestTimeoutDoesNotClearExclusions:
    def test_timeout_keeps_exclusions(self, bus, sm):
        _request_confirmation(bus, "X.mp3"); _drain()
        bus.publish(new_event(EVENT_CONFIRMATION_DENIED,
                              {"matched_file": "X.mp3"}, source="t")); _drain()
        # Then a TIMEOUT (kid said nothing) — exclusions stay so the kid can
        # retry and not get the same song back.
        bus.publish(new_event(EVENT_CONFIRMATION_TIMEOUT, source="t")); _drain()
        assert "X.mp3" in sm.excluded_files


class TestDenyEdgeCases:
    def test_deny_without_pending_is_noop(self, bus, sm):
        # No CONFIRMATION_REQUESTED first — just a stray DENY
        bus.publish(new_event(EVENT_CONFIRMATION_DENIED,
                              {"matched_file": "ghost.mp3"}, source="t")); _drain()
        # Should not crash, should not pollute excluded set
        assert sm.excluded_files == set()
        assert sm.consecutive_denies == 0

    def test_deny_with_no_matched_file_in_payload(self, bus, sm):
        _request_confirmation(bus, "X.mp3"); _drain()
        bus.publish(new_event(EVENT_CONFIRMATION_DENIED, {}, source="t")); _drain()
        # Falls back to using the pending file for exclusion
        assert "X.mp3" in sm.excluded_files


class TestDenyTelemetry:
    """The DENY event must carry the rejected file so /pisat-improve can mine it."""

    def test_deny_event_payload_has_matched_file(self, bus, sm):
        captured = []
        bus.subscribe(EVENT_CONFIRMATION_DENIED,
                      lambda e: captured.append(e))
        _request_confirmation(bus, "X.mp3"); _drain()
        bus.publish(new_event(EVENT_CONFIRMATION_DENIED,
                              {"matched_file": "X.mp3", "query": "x"},
                              source="reply_parser")); _drain()
        # The originally-published event is captured; payload preserved
        assert captured[0].payload.get("matched_file") == "X.mp3"
        assert captured[0].payload.get("query") == "x"
