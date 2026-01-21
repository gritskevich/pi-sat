import json
import os
from datetime import datetime, timezone
from typing import Any, Dict


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_interaction(path: str, payload: Dict[str, Any]) -> None:
    try:
        import config
    except Exception:
        config = None

    used_default_path = False
    if not path and config is not None:
        path = getattr(config, "INTERACTION_LOG_PATH", "")
        used_default_path = True

    if used_default_path and config is not None:
        mode = getattr(config, "INTERACTION_LOGGER", "jsonl")
        if mode == "none":
            return

    if not path:
        return
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    record = {"ts": _utc_now_iso(), **payload}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
