"""Test playback state resume after failed intent detection."""

import pytest
import time
from modules.playback_state_machine import PlaybackStateMachine
from modules.event_bus import EventBus
from modules.control_events import (
    new_event,
    EVENT_WAKE_WORD_DETECTED,
    EVENT_RECORDING_STARTED,
    EVENT_TTS_CONFIRMATION,
    EVENT_RECORDING_FINISHED,
    EVENT_PAUSE_REQUESTED,
    EVENT_CONTINUE_REQUESTED,
)


class MockMPDController:
    """Mock MPD controller for testing."""

    def __init__(self, initial_state="play"):
        self.state = initial_state
        self.events = []

    def get_status(self):
        return {"state": self.state}


def test_resume_after_no_intent_with_pre_playing_state():
    """Test that music resumes after wake word + no intent when music was playing."""
    # Setup
    event_bus = EventBus()
    event_bus.start()
    mpd = MockMPDController(initial_state="play")  # Music is playing
    state_machine = PlaybackStateMachine(event_bus, mpd_controller=mpd, debug=True)

    # Track events
    events_received = []

    def track_pause(event):
        events_received.append(("pause", event.payload))

    def track_continue(event):
        events_received.append(("continue", event.payload))

    event_bus.subscribe(EVENT_PAUSE_REQUESTED, track_pause)
    event_bus.subscribe(EVENT_CONTINUE_REQUESTED, track_continue)

    # Simulate wake word detection (music should pause)
    event_bus.publish(new_event(EVENT_WAKE_WORD_DETECTED, {"wake_word": "alexa_v0.1", "confidence": 0.5}))

    # Simulate recording started
    event_bus.publish(new_event(EVENT_RECORDING_STARTED, {}))

    # Simulate TTS confirmation with no intent (this happens BEFORE recording_finished in real system)
    event_bus.publish(new_event(EVENT_TTS_CONFIRMATION, {"intent_found": False, "reason": "no_intent"}))

    # Simulate recording finished (this happens AFTER tts_confirmation)
    event_bus.publish(new_event(EVENT_RECORDING_FINISHED, {}))

    # Wait for event bus to process all events
    time.sleep(0.1)

    # Check that we got both pause and continue events
    assert len([e for e in events_received if e[0] == "pause"]) >= 1, "Should have paused music"
    continue_events = [e for e in events_received if e[0] == "continue"]
    assert len(continue_events) == 1, f"Should have resumed music after no intent, got: {events_received}"
    assert continue_events[0][1].get("reason") in ["tts_no_intent", "recording_finished_no_intent"]


def test_no_resume_after_no_intent_when_music_was_paused():
    """Test that music does NOT resume if it was paused before wake word."""
    # Setup
    event_bus = EventBus()
    event_bus.start()
    mpd = MockMPDController(initial_state="pause")  # Music is NOT playing
    state_machine = PlaybackStateMachine(event_bus, mpd_controller=mpd, debug=True)

    # Track events
    events_received = []

    def track_pause(event):
        events_received.append(("pause", event.payload))

    def track_continue(event):
        events_received.append(("continue", event.payload))

    event_bus.subscribe(EVENT_PAUSE_REQUESTED, track_pause)
    event_bus.subscribe(EVENT_CONTINUE_REQUESTED, track_continue)

    # Simulate wake word detection (music is already paused, so no pause event)
    event_bus.publish(new_event(EVENT_WAKE_WORD_DETECTED, {"wake_word": "alexa_v0.1", "confidence": 0.5}))

    # Simulate recording started
    event_bus.publish(new_event(EVENT_RECORDING_STARTED, {}))

    # Simulate TTS confirmation with no intent
    event_bus.publish(new_event(EVENT_TTS_CONFIRMATION, {"intent_found": False, "reason": "no_intent"}))

    # Simulate recording finished
    event_bus.publish(new_event(EVENT_RECORDING_FINISHED, {}))

    # Wait for event bus to process all events
    time.sleep(0.1)

    # Check that we did NOT resume (since music was already paused)
    continue_events = [e for e in events_received if e[0] == "continue"]
    assert len(continue_events) == 0, f"Should NOT have resumed music when it was paused before, got: {events_received}"


def test_resume_after_valid_continue_intent():
    """Test that continue intent works correctly."""
    # Setup
    event_bus = EventBus()
    event_bus.start()
    mpd = MockMPDController(initial_state="pause")  # Music is paused
    state_machine = PlaybackStateMachine(event_bus, mpd_controller=mpd, debug=True)

    # Track events
    events_received = []

    def track_continue(event):
        events_received.append(("continue", event.payload))

    event_bus.subscribe(EVENT_CONTINUE_REQUESTED, track_continue)

    # Simulate wake word detection
    event_bus.publish(new_event(EVENT_WAKE_WORD_DETECTED, {"wake_word": "alexa_v0.1", "confidence": 0.5}))

    # Simulate recording started
    event_bus.publish(new_event(EVENT_RECORDING_STARTED, {}))

    # Simulate valid continue intent
    event_bus.publish(
        new_event(
            EVENT_TTS_CONFIRMATION,
            {"intent_found": True, "intent_type": "continue", "parameters": {}},
        )
    )

    # Simulate recording finished
    event_bus.publish(new_event(EVENT_RECORDING_FINISHED, {}))

    # Wait for event bus to process all events
    time.sleep(0.1)

    # Check that we got continue event
    continue_events = [e for e in events_received if e[0] == "continue"]
    assert len(continue_events) == 1, f"Should have resumed music with continue intent, got: {events_received}"
