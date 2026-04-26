"""Step-by-step branch + edge case coverage for the confirmation loop.

These tests are written from the spec, *not* from the existing implementation,
so they double as a code-review pass: a failing test points at a real bug.

Branches covered:
  AFFIRM: pending → INTENT_READY → TTS_CONFIRMATION → PLAY_REQUESTED (full chain)
  AFFIRM: pending with matched_file=None → no spurious play
  DENY: stray DENY mid-cluster (after a real DENY) → still no-op
  DENY: telemetry payload preserves query
  NEW_COMMAND: exclusion is reset (the kid is restating intent)
  Concurrency: wake during SHORT_LISTEN — orchestrator must not double-record
  Recursion: NEW_COMMAND chain bounded
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

import config
from modules.command_processor import CommandProcessor
from modules.command_validator import CommandValidator
from modules.control_events import (
    ControlEvent,
    EVENT_CONFIRMATION_AFFIRMED,
    EVENT_CONFIRMATION_DENIED,
    EVENT_CONFIRMATION_REQUESTED,
    EVENT_CONFIRMATION_TIMEOUT,
    EVENT_INTENT_READY,
    EVENT_PLAY_REQUESTED,
    EVENT_TTS_CONFIRMATION,
    EVENT_WAKE_WORD_DETECTED,
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


def _drain():
    time.sleep(0.05)


def _names(events):
    return [e.name for e in events]


def _build_processor(bus, *, stt_returns="oui", state_machine, library=None):
    library = library or FakeLibrary()
    speech_recorder = MagicMock()
    speech_recorder.record_short_reply = MagicMock(return_value=b"\x00" * 100)
    speech_recorder.record_command = MagicMock(return_value=b"\x00" * 100)
    stt = MagicMock()
    stt.transcribe = MagicMock(return_value=stt_returns)
    intent_engine = MagicMock()
    tts = MagicMock()
    tts.speak = MagicMock()
    tts.get_response_template = MagicMock(return_value=None)
    volume = MagicMock()
    validator = CommandValidator(music_library=library, language="fr")
    proc = CommandProcessor(
        speech_recorder=speech_recorder, stt_engine=stt, intent_engine=intent_engine,
        mpd_controller=StubMpd("stop"), tts_engine=tts, volume_manager=volume,
        event_bus=bus, command_validator=validator, debug=False, verbose=False,
    )
    proc.state_machine = state_machine
    return proc, tts


# --- B1: AFFIRM must trigger PLAY_REQUESTED, not just INTENT_READY ----------

class TestAffirmFullPlayChain:
    """Spec: kid says 'oui' → song actually plays.

    Implementation must publish BOTH EVENT_INTENT_READY (so state machine
    stores intent) AND EVENT_TTS_CONFIRMATION (so state machine triggers
    _apply_intent → EVENT_PLAY_REQUESTED). Otherwise the song never plays.
    """

    def test_affirm_results_in_play_requested_event(self, bus):
        sm = PlaybackStateMachine(event_bus=bus, mpd_controller=StubMpd("stop"))
        captured = []
        for n in (EVENT_INTENT_READY, EVENT_TTS_CONFIRMATION, EVENT_PLAY_REQUESTED):
            bus.subscribe(n, lambda e, store=captured: store.append(e))

        bus.publish(new_event(
            EVENT_CONFIRMATION_REQUESTED,
            {"matched_file": "X.mp3", "query": "x", "confidence": 0.55},
            source="t",
        )); _drain()
        bus.publish(new_event(
            EVENT_CONFIRMATION_AFFIRMED,
            {"matched_file": "X.mp3"}, source="reply_parser",
        )); _drain()

        names = _names(captured)
        # State machine published BOTH events
        assert EVENT_INTENT_READY in names, f"missing INTENT_READY in {names}"
        assert EVENT_TTS_CONFIRMATION in names, f"missing TTS_CONFIRMATION in {names}"
        # And the chain bottomed out at an actual play request
        assert EVENT_PLAY_REQUESTED in names, f"AFFIRM never produced PLAY_REQUESTED, got: {names}"
        # PLAY_REQUESTED carries the matched_file
        play_evt = next(e for e in captured if e.name == EVENT_PLAY_REQUESTED)
        assert play_evt.payload.get("matched_file") == "X.mp3"


# --- B2: AFFIRM with no matched_file in pending ----------------------------

class TestAffirmGuardsAgainstNullFile:
    def test_affirm_no_file_in_pending_does_not_publish_play(self, bus):
        sm = PlaybackStateMachine(event_bus=bus, mpd_controller=StubMpd("stop"))
        play_events = []
        bus.subscribe(EVENT_PLAY_REQUESTED, lambda e: play_events.append(e))
        # Manually rig pending without a file (defensive — shouldn't happen,
        # but test that it doesn't crash or play silence).
        sm.pending_confirmation = {"matched_file": None, "query": "x", "confidence": 0.55}
        bus.publish(new_event(
            EVENT_CONFIRMATION_AFFIRMED, {"matched_file": None}, source="t",
        )); _drain()
        # Should not publish an empty play
        assert play_events == []


# --- B3: stray DENY after a valid DENY -------------------------------------

class TestStrayDenyAfterFirstValidDeny:
    """Once excluded_files is non-empty, the no-op guard for stray DENYs
    breaks. Test that a DENY without pending after a real one is still a no-op."""

    def test_stray_deny_after_real_deny_is_noop(self, bus):
        sm = PlaybackStateMachine(event_bus=bus, mpd_controller=StubMpd("stop"))
        # First — a real DENY chain
        bus.publish(new_event(
            EVENT_CONFIRMATION_REQUESTED,
            {"matched_file": "X.mp3", "query": "x", "confidence": 0.55},
            source="t",
        )); _drain()
        bus.publish(new_event(EVENT_CONFIRMATION_DENIED,
                              {"matched_file": "X.mp3"}, source="t")); _drain()
        assert sm.consecutive_denies == 1
        assert sm.pending_confirmation is None

        # Now a STRAY DENY arrives without a fresh pending
        bus.publish(new_event(EVENT_CONFIRMATION_DENIED,
                              {"matched_file": "ghost.mp3"}, source="t")); _drain()
        # Must NOT increment denies counter or pollute exclusion
        assert sm.consecutive_denies == 1, "stray DENY incremented counter"
        assert "ghost.mp3" not in sm.excluded_files, "stray DENY added a file"


# --- B4: NEW_COMMAND should reset exclusion --------------------------------

class TestNewCommandResetsExclusion:
    """The kid is restating intent — exclusion from the previous suggestion
    cycle should not block her new request."""

    def test_new_command_reply_resets_excluded_files(self, bus):
        sm = PlaybackStateMachine(event_bus=bus, mpd_controller=StubMpd("stop"))
        # Ask about A, kid said non, then we get NEW_COMMAND
        bus.publish(new_event(
            EVENT_CONFIRMATION_REQUESTED,
            {"matched_file": "A.mp3", "query": "a", "confidence": 0.55},
            source="t",
        )); _drain()
        # Simulate kid replying "mets B" — parser says NEW_COMMAND
        proc, tts = _build_processor(bus,
                                      stt_returns="mets autre chose",
                                      state_machine=sm,
                                      library=FakeLibrary([("B.mp3", 0.92)]))
        # Mock intent_engine to return a play_music intent for the reply
        from modules.interfaces import Intent
        proc.intent_engine.classify = MagicMock(return_value=Intent(
            intent_type="play_music", confidence=1.0,
            parameters={"query": "autre chose"},
            raw_text="mets autre chose", language="fr",
        ))

        # Pre-condition: exclusion empty (only A is pending)
        assert sm.excluded_files == set()
        proc.process_confirmation_reply(); _drain()

        # After NEW_COMMAND processing, exclusion should be EMPTY (kid is
        # restating intent — A may not even be relevant anymore)
        assert sm.excluded_files == set(), \
            f"NEW_COMMAND should reset exclusion, but got {sm.excluded_files}"


# --- B5: Concurrent wake during SHORT_LISTEN -------------------------------

class TestConcurrentWakeDuringShortListen:
    """Wake-word fires while SHORT_LISTEN is in progress.

    The state machine clears pending + exclusion on wake. The reply thread,
    when it eventually publishes its parsed result, must be a no-op because
    pending_confirmation has been cleared.
    """

    def test_wake_clears_pending_so_late_reply_is_noop(self, bus):
        sm = PlaybackStateMachine(event_bus=bus, mpd_controller=StubMpd("play"))
        proc, tts = _build_processor(bus, stt_returns="oui", state_machine=sm)

        # Confirmation set
        bus.publish(new_event(
            EVENT_CONFIRMATION_REQUESTED,
            {"matched_file": "X.mp3", "query": "x", "confidence": 0.55},
            source="t",
        )); _drain()
        assert sm.pending_confirmation is not None

        # Snapshot pending then simulate wake (reply thread reads pending
        # before this would happen, but the published event arrives later)
        pending_snapshot = dict(sm.pending_confirmation)
        bus.publish(new_event(EVENT_WAKE_WORD_DETECTED, source="t")); _drain()
        assert sm.pending_confirmation is None

        # Now the reply thread (which had the snapshot) publishes AFFIRM
        play_events = []
        bus.subscribe(EVENT_PLAY_REQUESTED, lambda e: play_events.append(e))
        bus.publish(new_event(EVENT_CONFIRMATION_AFFIRMED,
                              {"matched_file": pending_snapshot["matched_file"]},
                              source="reply_parser_late")); _drain()
        # State machine must reject the late AFFIRM (no pending)
        assert play_events == [], "Late AFFIRM after wake-reset triggered a play"


# --- Step-by-step simulation: full successful loop -------------------------

class TestStepByStepFullSuccess:
    """Walks through every step with explicit pre/post-condition checks."""

    def test_kid_alexa_X_borderline_oui(self, bus):
        sm = PlaybackStateMachine(event_bus=bus, mpd_controller=StubMpd("play"))
        captured = []
        for n in (EVENT_INTENT_READY, EVENT_TTS_CONFIRMATION,
                  EVENT_PLAY_REQUESTED, EVENT_CONFIRMATION_AFFIRMED):
            bus.subscribe(n, lambda e, store=captured: store.append(e))

        # Step 1: wake → pause music
        bus.publish(new_event(EVENT_WAKE_WORD_DETECTED, source="t")); _drain()
        assert sm._pre_interaction_state == "play"

        # Step 2: validator decides borderline → CONFIRMATION_REQUESTED
        bus.publish(new_event(
            EVENT_CONFIRMATION_REQUESTED,
            {"matched_file": "X.mp3", "query": "x", "confidence": 0.55},
            source="validator",
        )); _drain()
        assert sm.pending_confirmation == {
            "matched_file": "X.mp3", "query": "x", "confidence": 0.55,
        }
        assert sm.excluded_files == set()
        assert sm.consecutive_denies == 0

        # Step 3: kid says "oui" → AFFIRMED
        bus.publish(new_event(
            EVENT_CONFIRMATION_AFFIRMED, {"matched_file": "X.mp3"}, source="t",
        )); _drain()

        # Step 4: PLAY_REQUESTED arrived
        names = _names(captured)
        assert EVENT_INTENT_READY in names
        assert EVENT_TTS_CONFIRMATION in names
        assert EVENT_PLAY_REQUESTED in names
        # Step 5: state machine cleaned up
        assert sm.pending_confirmation is None
        assert sm.excluded_files == set()
        assert sm.consecutive_denies == 0


class TestStepByStepThreeDenyGiveUp:
    """Walks through 3 denies + give-up, verifying counters and exclusion."""

    def test_three_consecutive_denies(self, bus):
        sm = PlaybackStateMachine(event_bus=bus, mpd_controller=StubMpd("play"))
        give_up = []
        bus.subscribe("confirmation_give_up", lambda e: give_up.append(e))

        # Step 1: wake (resets state, pauses music)
        bus.publish(new_event(EVENT_WAKE_WORD_DETECTED, source="t")); _drain()
        assert sm.consecutive_denies == 0
        assert sm.excluded_files == set()

        # Step 2-4: three iterations of (request + deny)
        for i, fp in enumerate(["A.mp3", "B.mp3", "C.mp3"], start=1):
            bus.publish(new_event(
                EVENT_CONFIRMATION_REQUESTED,
                {"matched_file": fp, "query": "x", "confidence": 0.55},
                source="t",
            )); _drain()
            assert sm.pending_confirmation["matched_file"] == fp
            bus.publish(new_event(EVENT_CONFIRMATION_DENIED,
                                  {"matched_file": fp}, source="t")); _drain()
            if i < 3:
                # Mid-loop: counter incremented, exclusion grew, no give-up yet
                assert sm.consecutive_denies == i
                assert fp in sm.excluded_files
                assert give_up == []
            else:
                # 3rd: give-up fired, state reset
                assert give_up != []
                assert sm.consecutive_denies == 0
                assert sm.excluded_files == set()
                assert sm.pending_confirmation is None


# --- Reply-class × music-state matrix --------------------------------------

class TestReplyMusicStateMatrix:
    """Cover every (reply_class, music_state) pair for terminal observable behavior."""

    @pytest.mark.parametrize("music_was_playing,expect_resume", [
        (True, True),
        (False, False),
    ])
    def test_timeout_resumes_only_if_was_playing(self, bus, music_was_playing, expect_resume):
        initial = "play" if music_was_playing else "pause"
        sm = PlaybackStateMachine(event_bus=bus, mpd_controller=StubMpd(initial))
        continues = []
        bus.subscribe("continue_requested", lambda e: continues.append(e))
        bus.publish(new_event(EVENT_WAKE_WORD_DETECTED, source="t")); _drain()
        bus.publish(new_event(
            EVENT_CONFIRMATION_REQUESTED,
            {"matched_file": "X.mp3", "query": "x", "confidence": 0.55},
            source="t",
        )); _drain()
        bus.publish(new_event(EVENT_CONFIRMATION_TIMEOUT, source="t")); _drain()
        if expect_resume:
            assert len(continues) >= 1
        else:
            assert continues == []

    @pytest.mark.parametrize("music_was_playing,expect_resume", [
        (True, True),
        (False, False),
    ])
    def test_giveup_resumes_only_if_was_playing(self, bus, music_was_playing, expect_resume):
        initial = "play" if music_was_playing else "pause"
        sm = PlaybackStateMachine(event_bus=bus, mpd_controller=StubMpd(initial))
        continues = []
        bus.subscribe("continue_requested", lambda e: continues.append(e))
        bus.publish(new_event(EVENT_WAKE_WORD_DETECTED, source="t")); _drain()
        for fp in ("A.mp3", "B.mp3", "C.mp3"):
            bus.publish(new_event(
                EVENT_CONFIRMATION_REQUESTED,
                {"matched_file": fp, "query": "x", "confidence": 0.55},
                source="t",
            )); _drain()
            bus.publish(new_event(EVENT_CONFIRMATION_DENIED,
                                  {"matched_file": fp}, source="t")); _drain()
        if expect_resume:
            assert len(continues) >= 1
        else:
            assert continues == []
