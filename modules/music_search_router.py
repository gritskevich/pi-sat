from modules.base_module import BaseModule
from modules.control_events import (
    ControlEvent,
    EVENT_MUSIC_SEARCH_REQUESTED,
    EVENT_MUSIC_RESOLVED,
    EVENT_PLAY_REQUESTED,
)
from modules.logging_utils import log_warning
from modules.music_resolver import MusicResolver


class MusicSearchRouter(BaseModule):
    """Resolve music queries and publish playback requests."""

    def __init__(self, event_bus, music_library, debug: bool = False):
        super().__init__(__name__, debug=debug, event_bus=event_bus)
        self.music_resolver = MusicResolver(music_library)
        self.event_bus.subscribe(EVENT_MUSIC_SEARCH_REQUESTED, self._on_search_requested)

    def _on_search_requested(self, event: ControlEvent):
        query = event.payload.get("query") or ""
        language = event.payload.get("language") or "fr"
        raw_text = event.payload.get("raw_text") or query

        resolution = self.music_resolver.resolve(raw_text, language, query)
        if not resolution:
            log_warning(self.logger, "Music search: no resolution")
            return

        resolved_payload = {
            "query": resolution.query,
            "matched_file": resolution.matched_file,
            "confidence": resolution.confidence,
        }
        self.event_bus.publish(
            ControlEvent.now(EVENT_MUSIC_RESOLVED, resolved_payload, source="music_search")
        )
        self.event_bus.publish(
            ControlEvent.now(EVENT_PLAY_REQUESTED, resolved_payload, source="music_search")
        )
