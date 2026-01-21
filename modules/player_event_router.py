from modules.control_events import (
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
    EVENT_RECORDING_STARTED,
    EVENT_RECORDING_FINISHED,
    ControlEvent,
)
import config
from modules.base_module import BaseModule
from modules.logging_utils import log_info, log_warning


class PlayerEventRouter(BaseModule):
    """Translate control events into MPD/volume actions."""

    def __init__(self, event_bus, mpd_controller, volume_manager, debug: bool = False):
        super().__init__(__name__, debug=debug, event_bus=event_bus)
        self.mpd_controller = mpd_controller
        self.volume_manager = volume_manager
        self._recording_active = False
        self._register_handlers()

    def _register_handlers(self):
        self.event_bus.subscribe(EVENT_VOLUME_UP_REQUESTED, self._on_volume_up)
        self.event_bus.subscribe(EVENT_VOLUME_DOWN_REQUESTED, self._on_volume_down)
        self.event_bus.subscribe(EVENT_PAUSE_REQUESTED, self._on_pause)
        self.event_bus.subscribe(EVENT_CONTINUE_REQUESTED, self._on_continue)
        self.event_bus.subscribe(EVENT_NEXT_TRACK_REQUESTED, self._on_next_track)
        self.event_bus.subscribe(EVENT_PREV_TRACK_REQUESTED, self._on_prev_track)
        self.event_bus.subscribe(EVENT_SET_VOLUME_REQUESTED, self._on_set_volume)
        self.event_bus.subscribe(EVENT_PLAY_REQUESTED, self._on_play_requested)
        self.event_bus.subscribe(EVENT_PLAY_FAVORITES_REQUESTED, self._on_play_favorites)
        self.event_bus.subscribe(EVENT_ADD_FAVORITE_REQUESTED, self._on_add_favorite)
        self.event_bus.subscribe(EVENT_SLEEP_TIMER_REQUESTED, self._on_sleep_timer)
        self.event_bus.subscribe(EVENT_REPEAT_MODE_REQUESTED, self._on_repeat_mode)
        self.event_bus.subscribe(EVENT_SHUFFLE_REQUESTED, self._on_shuffle)
        self.event_bus.subscribe(EVENT_QUEUE_ADD_REQUESTED, self._on_queue_add)
        self.event_bus.subscribe(EVENT_RECORDING_STARTED, self._on_recording_started)
        self.event_bus.subscribe(EVENT_RECORDING_FINISHED, self._on_recording_finished)

    def _on_recording_started(self, event: ControlEvent):
        self._recording_active = True
        try:
            status = self.mpd_controller.get_status()
            if status.get("state") == "play":
                self.mpd_controller.pause()
        except Exception as e:
            log_warning(self.logger, f"Recording pause failed: {e}")

    def _on_recording_finished(self, event: ControlEvent):
        self._recording_active = False

    def _ignore_if_recording(self, action: str) -> bool:
        if not self._recording_active:
            return False
        log_warning(self.logger, f"Event ignored during recording: {action}")
        return True

    def _on_volume_up(self, event: ControlEvent):
        log_info(self.logger, "Event: volume up")
        self.volume_manager.music_volume_up(config.VOLUME_STEP)

    def _on_volume_down(self, event: ControlEvent):
        log_info(self.logger, "Event: volume down")
        self.volume_manager.music_volume_down(config.VOLUME_STEP)

    def _on_pause(self, event: ControlEvent):
        log_info(self.logger, "Event: pause")
        self.mpd_controller.pause()

    def _on_continue(self, event: ControlEvent):
        if self._ignore_if_recording("continue"):
            return
        log_info(self.logger, "Event: continue")
        self._ensure_shuffle()
        self._resume_or_play()

    def _on_next_track(self, event: ControlEvent):
        if self._ignore_if_recording("next_track"):
            return
        log_info(self.logger, "Event: next track")
        self._ensure_shuffle()
        self.mpd_controller.next()

    def _on_prev_track(self, event: ControlEvent):
        if self._ignore_if_recording("previous_track"):
            return
        log_info(self.logger, "Event: previous track")
        self.mpd_controller.previous()

    def _on_set_volume(self, event: ControlEvent):
        volume = event.payload.get("volume")
        if volume is None:
            return
        self.volume_manager.set_music_volume(int(volume))

    def _on_play_requested(self, event: ControlEvent):
        if self._ignore_if_recording("play_requested"):
            return
        self._ensure_shuffle()
        query = event.payload.get("matched_file") or event.payload.get("query")
        self.mpd_controller.play(query)

    def _on_play_favorites(self, event: ControlEvent):
        if self._ignore_if_recording("play_favorites"):
            return
        self._ensure_shuffle()
        self.mpd_controller.play_favorites()

    def _on_add_favorite(self, event: ControlEvent):
        self.mpd_controller.add_to_favorites()

    def _on_sleep_timer(self, event: ControlEvent):
        minutes = event.payload.get("duration_minutes", 30)
        self.mpd_controller.set_sleep_timer(int(minutes))

    def _on_repeat_mode(self, event: ControlEvent):
        mode = event.payload.get("mode", "off")
        self.mpd_controller.set_repeat(mode)

    def _on_shuffle(self, event: ControlEvent):
        enabled = bool(event.payload.get("enabled", False))
        self.mpd_controller.set_shuffle(enabled)

    def _on_queue_add(self, event: ControlEvent):
        if self._ignore_if_recording("queue_add"):
            return
        query = event.payload.get("query")
        if not query:
            return
        play_next = bool(event.payload.get("play_next", False))
        self.mpd_controller.add_to_queue(query, play_next=play_next)

    def _ensure_shuffle(self):
        """Enforce shuffle mode if configured (domain invariant)."""
        if not getattr(config, "DEFAULT_SHUFFLE_MODE", False):
            return
        try:
            self.mpd_controller.set_shuffle(True)
        except Exception as e:
            log_warning(self.logger, f"Failed to ensure shuffle: {e}")

    def _resume_or_play(self):
        try:
            status = self.mpd_controller.get_status()
            state = status.get("state")
        except Exception as e:
            log_warning(self.logger, f"Failed to read MPD status ({e}); resuming anyway")
            self.mpd_controller.resume()
            return

        if state == "pause":
            self.mpd_controller.resume()
        elif state == "stop":
            self.mpd_controller.play()
        else:
            self.mpd_controller.resume()

    def _toggle_playback(self, event: ControlEvent):
        try:
            status = self.mpd_controller.get_status()
            state = status.get("state")
        except Exception as e:
            log_warning(self.logger, f"Failed to read MPD status ({e}); toggling resume")
            self._resume_or_play()
            return

        if state == "play":
            log_info(self.logger, "Event: toggle -> pause")
            self.mpd_controller.pause()
        elif state == "pause":
            log_info(self.logger, "Event: toggle -> resume")
            self.mpd_controller.resume()
        else:
            log_info(self.logger, "Event: toggle -> play")
            self.mpd_controller.play()
