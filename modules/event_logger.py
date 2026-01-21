import json
import os
from datetime import datetime, timezone


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EventLogger:
    """Minimal structured event logger (jsonl)."""

    def __init__(self, path: str, enabled: bool = True):
        self.path = path
        self.enabled = enabled

    def log(self, event) -> None:
        if not self.enabled or not self.path:
            return
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        record = {
            "ts": _utc_now_iso(),
            "event": event.name,
            "source": event.source,
            "payload": event.payload,
            "correlation_id": getattr(event, "correlation_id", None),
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
