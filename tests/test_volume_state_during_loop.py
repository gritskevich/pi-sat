"""Music state across the full confirmation+DENY loop.

"Volume off during listen, on after" maps to: music IS PAUSED throughout the
confirmation flow (no new audio competing with TTS or short-listen) and
RESUMES only on terminal exits (TIMEOUT/UNINTELLIGIBLE/give-up) — or the new
song plays on AFFIRM.
"""
from __future__ import annotations

import time

import pytest

import config
from modules.control_events import (
    ControlEvent,
    EVENT_CONFIRMATION_AFFIRMED,
    EVENT_CONFIRMATION_DENIED,
    EVENT_CONFIRMATION_GIVE_UP,
    EVENT_CONFIRMATION_REQUESTED,
    EVENT_CONFIRMATION_TIMEOUT,
    EVENT_CONTINUE_REQUESTED,
    EVENT_INTENT_READY,
    EVENT_MUSIC_SEARCH_REQUESTED,
    EVENT_PAUSE_REQUESTED,
    EVENT_PLAY_REQUESTED,
    EVENT_RECORDING_FINISHED,
    EVENT_RECORDING_STARTED,
    EVENT_TTS_CONFIRMATION,
    EVENT_WAKE_WORD_DETECTED,
    new_event,
)

# Any of these events fired during a pending confirmation would mean music
# is starting/resuming — i.e. the kid hears music when she should hear
# silence (waiting for her oui/non).
PLAY_INDUCING_EVENTS = (
    EVENT_CONTINUE_REQUESTED,
    EVENT_PLAY_REQUESTED,
    EVENT_MUSIC_SEARCH_REQUESTED,
)
from modules.event_bus import EventBus
from modules.playback_state_machine import PlaybackStateMachine


class StubMpd:
    def __init__(self, state="play"):
        self._state = state
    def get_status(self):
        return {"state": self._state}


@pytest.fixture
def bus(monkeypatch):
    monkeypatch.setattr(config, "EVENT_BUS_ENFORCE_WHITELIST", False, raising=False)
    monkeypatch.setattr(config, "EVENT_BUS_MAX_QUEUE", 100, raising=False)
    b = EventBus(debug=False); b.start(); yield b; b.stop()


@pytest.fixture
def captured(bus):
    events = []
    # Capture every event that could possibly start/resume playback during
    # what should be a silent confirmation window.
    for name in (
        EVENT_PAUSE_REQUESTED,
        EVENT_CONTINUE_REQUESTED,
        EVENT_PLAY_REQUESTED,
        EVENT_MUSIC_SEARCH_REQUESTED,
        EVENT_INTENT_READY,
    ):
        bus.subscribe(name, lambda e, store=events: store.append(e))
    return events


def _drain():
    time.sleep(0.05)


def _names(events):
    return [e.name for e in events]


class TestPauseOnWakeWhilePlaying:
    def test_wake_during_play_pauses(self, bus, captured):
        sm = PlaybackStateMachine(event_bus=bus, mpd_controller=StubMpd("play"))
        bus.publish(new_event(EVENT_WAKE_WORD_DETECTED, source="t")); _drain()
        assert EVENT_PAUSE_REQUESTED in _names(captured)


class TestNoResumeDuringConfirmationLoop:
    """While confirmation is pending or DENY-loop is running, don't auto-resume."""

    def test_no_continue_while_pending(self, bus, captured):
        """Music must NOT resume at any point in the confirmation lifecycle.

        Strict version: assert no CONTINUE_REQUESTED ever fires from wake
        through to short-listen completion. Earlier version cleared the
        captured list at the wrong point and missed a real bug where
        EVENT_TTS_CONFIRMATION with awaiting_confirmation=True fell through
        the state machine's "intent without _pending_intent" branch and
        spuriously published CONTINUE_REQUESTED.
        """
        sm = PlaybackStateMachine(event_bus=bus, mpd_controller=StubMpd("play"))
        # Wake → pause
        bus.publish(new_event(EVENT_WAKE_WORD_DETECTED, source="t")); _drain()
        bus.publish(new_event(EVENT_RECORDING_STARTED, source="t")); _drain()
        # Confirmation requested (validator decided low conf)
        bus.publish(new_event(EVENT_CONFIRMATION_REQUESTED,
                              {"matched_file": "X.mp3", "query": "x", "confidence": 0.55},
                              source="t")); _drain()
        bus.publish(new_event(EVENT_RECORDING_FINISHED, source="t")); _drain()
        # The validator/processor publishes TTS_CONFIRMATION with the awaiting
        # flag — at this point music MUST remain paused. NOTHING that could
        # cause playback (CONTINUE / PLAY / MUSIC_SEARCH) should fire.
        bus.publish(new_event(EVENT_TTS_CONFIRMATION,
                              {"intent_found": True, "intent_type": "play_music",
                               "awaiting_confirmation": True},
                              source="t")); _drain()
        play_events = [n for n in _names(captured) if n in {e for e in PLAY_INDUCING_EVENTS}]
        assert not play_events, (
            f"Music resumed during confirmation prompt; play-inducing events: {play_events}"
        )
        # Short-listen cycle starts (kid's reply is being captured)
        bus.publish(new_event(EVENT_RECORDING_STARTED, source="t")); _drain()
        bus.publish(new_event(EVENT_RECORDING_FINISHED, source="t")); _drain()
        play_events = [n for n in _names(captured) if n in {e for e in PLAY_INDUCING_EVENTS}]
        assert not play_events, (
            f"Music resumed after short-listen recording finished; events: {play_events}"
        )
        assert sm.pending_confirmation is not None

    def test_deny_does_not_resume_music(self, bus, captured):
        sm = PlaybackStateMachine(event_bus=bus, mpd_controller=StubMpd("play"))
        bus.publish(new_event(EVENT_WAKE_WORD_DETECTED, source="t")); _drain()
        bus.publish(new_event(EVENT_CONFIRMATION_REQUESTED,
                              {"matched_file": "X.mp3", "query": "x", "confidence": 0.55},
                              source="t")); _drain()
        captured.clear()
        # Kid said "non" — we discard pending, listen for new command, music
        # must stay paused (the kid is still mid-conversation).
        bus.publish(new_event(EVENT_CONFIRMATION_DENIED,
                              {"matched_file": "X.mp3"}, source="t")); _drain()
        assert EVENT_CONTINUE_REQUESTED not in _names(captured)


class TestResumeOnTerminalExits:
    def test_timeout_resumes_previously_playing_music(self, bus, captured):
        sm = PlaybackStateMachine(event_bus=bus, mpd_controller=StubMpd("play"))
        bus.publish(new_event(EVENT_WAKE_WORD_DETECTED, source="t")); _drain()
        bus.publish(new_event(EVENT_CONFIRMATION_REQUESTED,
                              {"matched_file": "X.mp3", "query": "x", "confidence": 0.55},
                              source="t")); _drain()
        captured.clear()
        bus.publish(new_event(EVENT_CONFIRMATION_TIMEOUT, source="t")); _drain()
        # Music must come back
        assert EVENT_CONTINUE_REQUESTED in _names(captured)

    def test_give_up_after_3_denies_resumes_music(self, bus, captured):
        sm = PlaybackStateMachine(event_bus=bus, mpd_controller=StubMpd("play"))
        bus.publish(new_event(EVENT_WAKE_WORD_DETECTED, source="t")); _drain()
        for fp in ("A.mp3", "B.mp3", "C.mp3"):
            bus.publish(new_event(EVENT_CONFIRMATION_REQUESTED,
                                  {"matched_file": fp, "query": "x", "confidence": 0.55},
                                  source="t")); _drain()
            bus.publish(new_event(EVENT_CONFIRMATION_DENIED,
                                  {"matched_file": fp}, source="t")); _drain()
        # 3rd DENY → give-up. Music should resume.
        # The give-up handler publishes CONTINUE if we were playing pre-interaction.
        captured_after_giveup = [e for e in captured]
        assert EVENT_CONTINUE_REQUESTED in _names(captured_after_giveup)


class TestPausedMusicStaysPaused:
    """If the kid woke the box from PAUSED state, give-up should not resume."""

    def test_giveup_with_no_prior_playback_does_not_resume(self, bus, captured):
        sm = PlaybackStateMachine(event_bus=bus, mpd_controller=StubMpd("pause"))
        bus.publish(new_event(EVENT_WAKE_WORD_DETECTED, source="t")); _drain()
        # No PAUSE was emitted (already paused)
        assert EVENT_PAUSE_REQUESTED not in _names(captured)
        for fp in ("A.mp3", "B.mp3", "C.mp3"):
            bus.publish(new_event(EVENT_CONFIRMATION_REQUESTED,
                                  {"matched_file": fp, "query": "x", "confidence": 0.55},
                                  source="t")); _drain()
            bus.publish(new_event(EVENT_CONFIRMATION_DENIED,
                                  {"matched_file": fp}, source="t")); _drain()
        # Was paused before — should not auto-CONTINUE on give-up
        assert EVENT_CONTINUE_REQUESTED not in _names(captured)


class TestAffirmTriggersIntentReady:
    def test_affirm_publishes_intent_ready_with_pending(self, bus, captured):
        sm = PlaybackStateMachine(event_bus=bus, mpd_controller=StubMpd("play"))
        bus.publish(new_event(EVENT_WAKE_WORD_DETECTED, source="t")); _drain()
        bus.publish(new_event(EVENT_CONFIRMATION_REQUESTED,
                              {"matched_file": "X.mp3", "query": "x", "confidence": 0.55},
                              source="t")); _drain()
        captured.clear()
        bus.publish(new_event(EVENT_CONFIRMATION_AFFIRMED,
                              {"matched_file": "X.mp3"}, source="t")); _drain()
        intent_events = [e for e in captured if e.name == EVENT_INTENT_READY]
        assert len(intent_events) == 1
        params = intent_events[0].payload.get("parameters", {})
        assert params.get("matched_file") == "X.mp3"


class TestExclusionAcrossPause:
    def test_exclusion_persists_across_pause_state(self, bus):
        """Music being played/paused does NOT affect exclusion set lifecycle."""
        sm = PlaybackStateMachine(event_bus=bus, mpd_controller=StubMpd("play"))
        bus.publish(new_event(EVENT_CONFIRMATION_REQUESTED,
                              {"matched_file": "X.mp3", "query": "x", "confidence": 0.55},
                              source="t")); _drain()
        bus.publish(new_event(EVENT_CONFIRMATION_DENIED,
                              {"matched_file": "X.mp3"}, source="t")); _drain()
        assert "X.mp3" in sm.excluded_files
        # MPD state changes externally — exclusion should not care
        sm.mpd_controller._state = "pause"
        # Still in exclusion
        assert "X.mp3" in sm.excluded_files
