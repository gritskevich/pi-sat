from dataclasses import dataclass
from typing import Any, Dict, Optional, Set
import time


EVENT_BUTTON_PRESSED = "button_pressed"
EVENT_BUTTON_DOUBLE_PRESSED = "button_double_pressed"
EVENT_VOLUME_UP_REQUESTED = "volume_up_requested"
EVENT_VOLUME_DOWN_REQUESTED = "volume_down_requested"
EVENT_PAUSE_REQUESTED = "pause_requested"
EVENT_CONTINUE_REQUESTED = "continue_requested"
EVENT_NEXT_TRACK_REQUESTED = "next_track_requested"
EVENT_PREV_TRACK_REQUESTED = "previous_track_requested"
EVENT_SET_VOLUME_REQUESTED = "set_volume_requested"
EVENT_PLAY_REQUESTED = "play_requested"
EVENT_PLAY_FAVORITES_REQUESTED = "play_favorites_requested"
EVENT_ADD_FAVORITE_REQUESTED = "add_favorite_requested"
EVENT_SLEEP_TIMER_REQUESTED = "sleep_timer_requested"
EVENT_REPEAT_MODE_REQUESTED = "repeat_mode_requested"
EVENT_SHUFFLE_REQUESTED = "shuffle_requested"
EVENT_QUEUE_ADD_REQUESTED = "queue_add_requested"
EVENT_MUSIC_SEARCH_REQUESTED = "music_search_requested"
EVENT_MUSIC_RESOLVED = "music_resolved"
EVENT_INTENT_DETECTED = "intent_detected"
EVENT_RECORDING_STARTED = "recording_started"
EVENT_RECORDING_FINISHED = "recording_finished"
EVENT_WAKE_WORD_DETECTED = "wake_word_detected"
EVENT_INTENT_READY = "intent_ready"
EVENT_TTS_CONFIRMATION = "tts_confirmation"


@dataclass(frozen=True)
class ControlEvent:
    name: str
    payload: Dict[str, Any]
    timestamp: float
    source: Optional[str] = None
    correlation_id: Optional[str] = None

    @staticmethod
    def now(
        name: str,
        payload: Optional[Dict[str, Any]] = None,
        source: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> "ControlEvent":
        return ControlEvent(
            name=name,
            payload=payload or {},
            timestamp=time.time(),
            source=source,
            correlation_id=correlation_id,
        )


def new_event(
    name: str,
    payload: Optional[Dict[str, Any]] = None,
    source: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> ControlEvent:
    """Helper to create ControlEvent with consistent metadata."""
    return ControlEvent.now(
        name=name,
        payload=payload,
        source=source,
        correlation_id=correlation_id,
    )


ALLOWED_EVENTS: Set[str] = {
    EVENT_BUTTON_PRESSED,
    EVENT_BUTTON_DOUBLE_PRESSED,
    EVENT_VOLUME_UP_REQUESTED,
    EVENT_VOLUME_DOWN_REQUESTED,
    EVENT_PAUSE_REQUESTED,
    EVENT_CONTINUE_REQUESTED,
    EVENT_NEXT_TRACK_REQUESTED,
    EVENT_PREV_TRACK_REQUESTED,
    EVENT_SET_VOLUME_REQUESTED,
    EVENT_PLAY_REQUESTED,
    EVENT_PLAY_FAVORITES_REQUESTED,
    EVENT_ADD_FAVORITE_REQUESTED,
    EVENT_SLEEP_TIMER_REQUESTED,
    EVENT_REPEAT_MODE_REQUESTED,
    EVENT_SHUFFLE_REQUESTED,
    EVENT_QUEUE_ADD_REQUESTED,
    EVENT_MUSIC_SEARCH_REQUESTED,
    EVENT_MUSIC_RESOLVED,
    EVENT_INTENT_DETECTED,
    EVENT_RECORDING_STARTED,
    EVENT_RECORDING_FINISHED,
    EVENT_WAKE_WORD_DETECTED,
    EVENT_INTENT_READY,
    EVENT_TTS_CONFIRMATION,
}
