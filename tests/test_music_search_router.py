from modules.control_events import (
    ControlEvent,
    EVENT_MUSIC_SEARCH_REQUESTED,
    EVENT_MUSIC_RESOLVED,
    EVENT_PLAY_REQUESTED,
)
from modules.music_search_router import MusicSearchRouter


class FakeEventBus:
    def __init__(self):
        self.handlers = {}
        self.events = []

    def subscribe(self, name, handler):
        self.handlers.setdefault(name, []).append(handler)

    def publish(self, event):
        self.events.append(event)
        for handler in self.handlers.get(event.name, []):
            handler(event)
        return True


class FakeLibrary:
    def search_best(self, query):
        return ("maman.mp3", 0.9)


def test_music_search_router_emits_resolution_and_play_request():
    bus = FakeEventBus()
    library = FakeLibrary()
    MusicSearchRouter(event_bus=bus, music_library=library, debug=False)

    bus.publish(
        ControlEvent.now(
            EVENT_MUSIC_SEARCH_REQUESTED,
            {"query": "maman", "raw_text": "joue maman", "language": "fr"},
            source="test"
        )
    )

    names = [event.name for event in bus.events]
    assert EVENT_MUSIC_RESOLVED in names
    assert EVENT_PLAY_REQUESTED in names
