import queue
import threading
from typing import Callable, Dict, List

import config
from modules.control_events import ControlEvent, ALLOWED_EVENTS
from modules.logging_utils import setup_logger, log_debug, log_warning


class EventBus:
    """Simple in-process event bus with a background dispatcher thread."""

    def __init__(self, debug: bool = False):
        self._handlers: Dict[str, List[Callable[[ControlEvent], None]]] = {}
        self._all_handlers: List[Callable[[ControlEvent], None]] = []
        maxsize = int(getattr(config, "EVENT_BUS_MAX_QUEUE", 1000))
        self._drop_policy = getattr(config, "EVENT_BUS_DROP_POLICY", "drop_new").lower()
        self._enforce_whitelist = bool(getattr(config, "EVENT_BUS_ENFORCE_WHITELIST", True))
        self._allowed_events = set(ALLOWED_EVENTS)
        self._queue: "queue.Queue[ControlEvent]" = queue.Queue(maxsize=maxsize)
        self._stats = {
            "published": 0,
            "dropped": 0,
            "dropped_full": 0,
            "dropped_oldest": 0,
            "dropped_new": 0,
            "last_drop_event": None,
            "last_drop_reason": None,
        }
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self.debug = debug
        self.logger = setup_logger(__name__, debug=debug)

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._dispatch_loop, daemon=True)
        self._thread.start()
        log_debug(self.logger, "EventBus dispatcher started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None
        log_debug(self.logger, "EventBus dispatcher stopped")

    def subscribe(self, event_name: str, handler: Callable[[ControlEvent], None]):
        with self._lock:
            self._handlers.setdefault(event_name, []).append(handler)

    def subscribe_all(self, handler: Callable[[ControlEvent], None]):
        with self._lock:
            self._all_handlers.append(handler)

    def publish(self, event: ControlEvent) -> bool:
        if not self._running:
            log_warning(self.logger, f"EventBus not running; dropping event: {event.name}")
            return False
        if self._enforce_whitelist and event.name not in self._allowed_events:
            log_warning(self.logger, f"EventBus unknown event: {event.name}")
            return False
        try:
            self._queue.put_nowait(event)
            self._stats["published"] += 1
        except queue.Full:
            if self._drop_policy == "drop_oldest":
                try:
                    self._queue.get_nowait()
                    self._queue.task_done()
                    self._record_drop(event_name="oldest", reason="drop_oldest")
                except queue.Empty:
                    pass
                try:
                    self._queue.put_nowait(event)
                    self._stats["published"] += 1
                except queue.Full:
                    self._record_drop(event_name=event.name, reason="drop_new")
                    log_warning(self.logger, f"EventBus queue full; dropping event: {event.name}")
                    return False
            else:
                self._record_drop(event_name=event.name, reason="drop_new")
                log_warning(self.logger, f"EventBus queue full; dropping event: {event.name}")
                return False
        return True

    def _record_drop(self, event_name: str, reason: str):
        self._stats["dropped"] += 1
        self._stats["dropped_full"] += 1
        if reason == "drop_oldest":
            self._stats["dropped_oldest"] += 1
        else:
            self._stats["dropped_new"] += 1
        self._stats["last_drop_event"] = event_name
        self._stats["last_drop_reason"] = reason

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _dispatch_loop(self):
        while self._running or not self._queue.empty():
            try:
                event = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue

            with self._lock:
                handlers = list(self._handlers.get(event.name, []))
                handlers.extend(self._all_handlers)

            if self.debug:
                log_debug(self.logger, f"Dispatching event: {event.name} ({len(handlers)} handlers)")

            for handler in handlers:
                try:
                    handler(event)
                except Exception as e:
                    log_warning(self.logger, f"Event handler error for {event.name}: {e}")

            self._queue.task_done()
