from modules.base_module import BaseModule
from modules.control_events import (
    ControlEvent,
    new_event,
    EVENT_ADD_FAVORITE_REQUESTED,
    EVENT_BUTTON_DOUBLE_PRESSED,
    EVENT_BUTTON_PRESSED,
    EVENT_CONTINUE_REQUESTED,
    EVENT_INTENT_READY,
    EVENT_MUSIC_SEARCH_REQUESTED,
    EVENT_NEXT_TRACK_REQUESTED,
    EVENT_PAUSE_REQUESTED,
    EVENT_PLAY_FAVORITES_REQUESTED,
    EVENT_PLAY_REQUESTED,
    EVENT_PREV_TRACK_REQUESTED,
    EVENT_QUEUE_ADD_REQUESTED,
    EVENT_RECORDING_FINISHED,
    EVENT_RECORDING_STARTED,
    EVENT_REPEAT_MODE_REQUESTED,
    EVENT_SET_VOLUME_REQUESTED,
    EVENT_SHUFFLE_REQUESTED,
    EVENT_SLEEP_TIMER_REQUESTED,
    EVENT_TTS_CONFIRMATION,
    EVENT_VOLUME_DOWN_REQUESTED,
    EVENT_VOLUME_UP_REQUESTED,
    EVENT_WAKE_WORD_DETECTED,
    EVENT_CONFIRMATION_REQUESTED,
    EVENT_CONFIRMATION_AFFIRMED,
    EVENT_CONFIRMATION_DENIED,
    EVENT_CONFIRMATION_TIMEOUT,
    EVENT_CONFIRMATION_GIVE_UP,
)
from modules.logging_utils import log_debug, log_warning


class PlaybackStateMachine(BaseModule):
    """Centralized playback state decisions from neutral events."""

    def __init__(self, event_bus, mpd_controller=None, debug: bool = False):
        super().__init__(__name__, debug=debug, event_bus=event_bus)
        self.mpd_controller = mpd_controller
        self._playback_state = self._read_state()
        self._recording_active = False
        self._pre_interaction_state = None
        self._pending_intent = None
        self._interaction_active = False
        self._should_resume_after_recording = False
        # Confirmation lane: a borderline-confidence play_music match where the
        # TTS asked "Tu veux X ?" instead of playing. We park the candidate here
        # until a follow-up (a yes/no parsed from the kid's next utterance, or
        # a fresh wake word that supersedes it). dict shape:
        #   {"matched_file": "X.mp3", "query": "...", "confidence": float}
        self.pending_confirmation: dict | None = None
        # Songs the kid has DENY'd in this cluster — passed to MusicLibrary.search_best
        # so the same wrong match does not get re-proposed in the loop.
        self.excluded_files: set[str] = set()
        # 3rd consecutive DENY → give-up (avoids infinite "désolée" loops).
        self.consecutive_denies: int = 0
        self.MAX_CONSECUTIVE_DENIES: int = 3
        self.event_bus.subscribe(EVENT_WAKE_WORD_DETECTED, self._on_wake_word_detected)
        self.event_bus.subscribe(EVENT_BUTTON_PRESSED, self._on_button_pressed)
        self.event_bus.subscribe(EVENT_BUTTON_DOUBLE_PRESSED, self._on_button_double_pressed)
        self.event_bus.subscribe(EVENT_RECORDING_STARTED, self._on_recording_started)
        self.event_bus.subscribe(EVENT_RECORDING_FINISHED, self._on_recording_finished)
        self.event_bus.subscribe(EVENT_INTENT_READY, self._on_intent_ready)
        self.event_bus.subscribe(EVENT_TTS_CONFIRMATION, self._on_tts_confirmation)
        self.event_bus.subscribe(EVENT_CONFIRMATION_REQUESTED, self._on_confirmation_requested)
        self.event_bus.subscribe(EVENT_CONFIRMATION_AFFIRMED, self._on_confirmation_affirmed)
        self.event_bus.subscribe(EVENT_CONFIRMATION_DENIED, self._on_confirmation_denied)
        self.event_bus.subscribe(EVENT_CONFIRMATION_TIMEOUT, self._on_confirmation_timeout)

    def _read_state(self) -> str:
        if not self.mpd_controller:
            return "unknown"
        try:
            status = self.mpd_controller.get_status()
            return status.get("state") or "unknown"
        except Exception as e:
            log_warning(self.logger, f"State read failed: {e}")
            return "unknown"

    def _set_state(self, new_state: str):
        self._playback_state = new_state

    def _pause_if_playing(self, reason: str):
        state = self._playback_state if self._playback_state != "unknown" else self._read_state()
        if state == "play":
            self.event_bus.publish(
                new_event(EVENT_PAUSE_REQUESTED, {"reason": reason}, source="state_machine")
            )
            self._set_state("pause")
            if self._pre_interaction_state is None:
                self._pre_interaction_state = "play"
        self._interaction_active = True

    def _resume_if_needed(self, reason: str):
        if self._recording_active:
            # If recording is still active, defer resume until recording finishes
            self._should_resume_after_recording = True
            return
        if self._pre_interaction_state == "play":
            self.event_bus.publish(
                new_event(EVENT_CONTINUE_REQUESTED, {"reason": reason}, source="state_machine")
            )
            self._set_state("play")
        self._pre_interaction_state = None
        self._interaction_active = False
        self._should_resume_after_recording = False

    def _on_wake_word_detected(self, event: ControlEvent):
        # Fresh wake word — any prior pending confirmation is now stale (the
        # kid is asking again, presumably because the previous question was
        # for the wrong song). Reset the whole cluster's exclusion + counter:
        # this is a fresh session.
        if self.pending_confirmation is not None:
            log_debug(
                self.logger,
                f"Dropping pending confirmation due to new wake word: "
                f"{self.pending_confirmation.get('matched_file')}",
            )
            self.pending_confirmation = None
        self.excluded_files = set()
        self.consecutive_denies = 0
        self._pause_if_playing("wake_word_detected")

    def _on_confirmation_requested(self, event: ControlEvent):
        payload = event.payload or {}
        if not payload.get("matched_file"):
            log_warning(self.logger, "Confirmation requested without matched_file; ignoring")
            return
        self.pending_confirmation = {
            "matched_file": payload.get("matched_file"),
            "query": payload.get("query"),
            "confidence": payload.get("confidence", 0.0),
        }
        log_debug(
            self.logger,
            f"Awaiting confirmation for {self.pending_confirmation['matched_file']} "
            f"(conf={self.pending_confirmation['confidence']:.2f})",
        )

    def _on_confirmation_affirmed(self, event: ControlEvent):
        """Kid said 'oui' — play the pending candidate, reset the loop state."""
        pending = self.pending_confirmation
        if pending is None:
            log_debug(self.logger, "AFFIRM with no pending; ignoring")
            return
        # Trigger play via the standard pipeline event
        self.event_bus.publish(new_event(
            EVENT_INTENT_READY,
            {
                "intent_type": "play_music",
                "parameters": {
                    "matched_file": pending["matched_file"],
                    "query": pending.get("query"),
                },
                "raw_text": pending.get("query"),
                "language": "fr",
            },
            source="state_machine",
        ))
        # Reset confirmation lane for the next cluster
        self.pending_confirmation = None
        self.excluded_files = set()
        self.consecutive_denies = 0

    def _on_confirmation_denied(self, event: ControlEvent):
        """Kid said 'non' — exclude the song, increment denies counter, give up after 3."""
        payload = event.payload or {}
        # Resolve the file to exclude: prefer payload, fall back to pending
        rejected_file = payload.get("matched_file")
        if not rejected_file and self.pending_confirmation:
            rejected_file = self.pending_confirmation.get("matched_file")

        if not rejected_file:
            log_debug(self.logger, "DENY with no file context; ignoring")
            return

        # Stray DENY without any pending or prior request — no-op
        if self.pending_confirmation is None and not self.excluded_files:
            log_debug(self.logger, f"Stray DENY for {rejected_file!r}; ignoring")
            return

        self.excluded_files.add(rejected_file)
        self.consecutive_denies += 1
        # Pending is consumed — caller (orchestrator) will start the next listen/match
        self.pending_confirmation = None

        if self.consecutive_denies >= self.MAX_CONSECUTIVE_DENIES:
            self._give_up()

    def _give_up(self):
        """3rd DENY — give up the cluster, resume previous music if any."""
        denied = sorted(self.excluded_files)
        self.event_bus.publish(new_event(
            EVENT_CONFIRMATION_GIVE_UP,
            {"reason": "max_denies", "denied_files": denied},
            source="state_machine",
        ))
        # Reset for a fresh start
        self.excluded_files = set()
        self.consecutive_denies = 0
        self.pending_confirmation = None
        # If music was paused for the interaction, bring it back
        self._resume_if_needed("confirmation_give_up")

    def _on_confirmation_timeout(self, event: ControlEvent):
        """Kid stayed silent — drop pending, keep exclusion (cluster lives), resume music."""
        self.pending_confirmation = None
        # Note: do NOT reset excluded_files — the kid may retry within the cluster
        self._resume_if_needed("confirmation_timeout")

    def _on_button_pressed(self, event: ControlEvent):
        if self._recording_active or self._interaction_active:
            return
        state = self._playback_state if self._playback_state != "unknown" else self._read_state()
        if state == "play":
            self.event_bus.publish(new_event(EVENT_PAUSE_REQUESTED, source="state_machine"))
            self._set_state("pause")
        else:
            self.event_bus.publish(new_event(EVENT_CONTINUE_REQUESTED, source="state_machine"))
            self._set_state("play")

    def _on_button_double_pressed(self, event: ControlEvent):
        if self._recording_active or self._interaction_active:
            return
        self.event_bus.publish(new_event(EVENT_NEXT_TRACK_REQUESTED, source="state_machine"))

    def _on_recording_started(self, event: ControlEvent):
        self._recording_active = True
        self._interaction_active = True
        self._pause_if_playing("recording_started")

    def _on_recording_finished(self, event: ControlEvent):
        self._recording_active = False
        # If we deferred resume due to active recording, resume now
        if self._should_resume_after_recording:
            self._resume_if_needed("recording_finished_no_intent")

    def _on_intent_ready(self, event: ControlEvent):
        self._pending_intent = dict(event.payload or {})

    def _on_tts_confirmation(self, event: ControlEvent):
        intent_found = bool(event.payload.get("intent_found", False))
        if not intent_found:
            self._pending_intent = None
            self._resume_if_needed("tts_no_intent")
            return

        pending = self._pending_intent or {}
        intent_type = pending.get("intent_type") or event.payload.get("intent_type")
        if not intent_type:
            self._resume_if_needed("tts_missing_intent")
            return

        self._apply_intent(intent_type, pending)
        self._pending_intent = None

        # Resume playback if intent didn't explicitly change playback state
        if self._is_playback_neutral_intent(intent_type):
            self._resume_if_needed(f"tts_after_{intent_type}")
        else:
            # Playback-changing intents manage state themselves
            self._pre_interaction_state = None
            self._interaction_active = False

    def _is_playback_neutral_intent(self, intent_type: str) -> bool:
        """Check if intent doesn't change playback state (pause/play/stop).

        Playback-neutral intents should resume music if it was playing before.
        Playback-changing intents manage their own state transitions.
        """
        PLAYBACK_NEUTRAL_INTENTS = {
            "volume_up",
            "volume_down",
            "set_volume",
            "add_favorite",
            "sleep_timer",
            "repeat",
            "shuffle",
            "queue_add",
            "next",
            "previous",
        }
        return intent_type in PLAYBACK_NEUTRAL_INTENTS

    def _apply_intent(self, intent_type: str, payload: dict):
        parameters = payload.get("parameters") or {}
        if intent_type == "play_music":
            matched_file = parameters.get("matched_file")
            if matched_file:
                self.event_bus.publish(
                    new_event(
                        EVENT_PLAY_REQUESTED,
                        {"matched_file": matched_file, "query": parameters.get("query")},
                        source="state_machine",
                    )
                )
            else:
                query = parameters.get("query")
                self.event_bus.publish(
                    new_event(
                        EVENT_MUSIC_SEARCH_REQUESTED,
                        {"query": query, "raw_text": payload.get("raw_text"), "language": payload.get("language")},
                        source="state_machine",
                    )
                )
            self._set_state("play")
        elif intent_type == "play_favorites":
            self.event_bus.publish(new_event(EVENT_PLAY_FAVORITES_REQUESTED, source="state_machine"))
            self._set_state("play")
        elif intent_type in ("pause", "stop"):
            self.event_bus.publish(new_event(EVENT_PAUSE_REQUESTED, source="state_machine"))
            self._set_state("pause")
        elif intent_type in ("continue", "resume"):
            self.event_bus.publish(new_event(EVENT_CONTINUE_REQUESTED, source="state_machine"))
            self._set_state("play")
        elif intent_type == "next":
            self.event_bus.publish(new_event(EVENT_NEXT_TRACK_REQUESTED, source="state_machine"))
        elif intent_type == "previous":
            self.event_bus.publish(new_event(EVENT_PREV_TRACK_REQUESTED, source="state_machine"))
        elif intent_type == "volume_up":
            self.event_bus.publish(new_event(EVENT_VOLUME_UP_REQUESTED, source="state_machine"))
        elif intent_type == "volume_down":
            self.event_bus.publish(new_event(EVENT_VOLUME_DOWN_REQUESTED, source="state_machine"))
        elif intent_type == "set_volume":
            volume = parameters.get("volume")
            if volume is None:
                return
            self.event_bus.publish(
                new_event(EVENT_SET_VOLUME_REQUESTED, {"volume": volume}, source="state_machine")
            )
        elif intent_type == "add_favorite":
            self.event_bus.publish(new_event(EVENT_ADD_FAVORITE_REQUESTED, source="state_machine"))
        elif intent_type == "sleep_timer":
            minutes = parameters.get("duration_minutes", 30)
            self.event_bus.publish(
                new_event(
                    EVENT_SLEEP_TIMER_REQUESTED,
                    {"duration_minutes": minutes},
                    source="state_machine",
                )
            )
        elif intent_type == "repeat":
            mode = parameters.get("mode", "off")
            self.event_bus.publish(
                new_event(EVENT_REPEAT_MODE_REQUESTED, {"mode": mode}, source="state_machine")
            )
        elif intent_type == "shuffle":
            enabled = bool(parameters.get("enabled", False))
            self.event_bus.publish(
                new_event(EVENT_SHUFFLE_REQUESTED, {"enabled": enabled}, source="state_machine")
            )
        elif intent_type == "queue_add":
            query = parameters.get("query")
            if not query:
                return
            play_next = bool(parameters.get("play_next", False))
            self.event_bus.publish(
                new_event(
                    EVENT_QUEUE_ADD_REQUESTED,
                    {"query": query, "play_next": play_next},
                    source="state_machine",
                )
            )
        else:
            log_debug(self.logger, f"StateMachine: ignoring intent '{intent_type}'")
