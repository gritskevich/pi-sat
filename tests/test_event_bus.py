import time

import config
from modules.control_events import ControlEvent
from modules.event_bus import EventBus


def test_event_bus_drop_oldest(monkeypatch):
    monkeypatch.setattr(config, "EVENT_BUS_MAX_QUEUE", 1)
    monkeypatch.setattr(config, "EVENT_BUS_DROP_POLICY", "drop_oldest")
    monkeypatch.setattr(config, "EVENT_BUS_ENFORCE_WHITELIST", False)

    bus = EventBus(debug=False)
    received = []

    def handler(event):
        received.append(event.name)

    bus.subscribe("evt", handler)
    bus.start()

    bus.publish(ControlEvent.now("evt", source="test"))
    bus.publish(ControlEvent.now("evt", source="test"))

    time.sleep(0.05)
    bus.stop()

    stats = bus.get_stats()
    assert stats["dropped_oldest"] == 1
    assert stats["last_drop_reason"] == "drop_oldest"
