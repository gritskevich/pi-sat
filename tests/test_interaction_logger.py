import json
import os
import tempfile

from modules.interaction_logger import append_interaction


def test_append_interaction_jsonl():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    try:
        append_interaction(path, {"text": "bonjour", "intent": "play_music"})
        append_interaction(path, {"text": "plus fort", "intent": "volume_up"})

        with open(path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]

        assert len(lines) == 2
        first = json.loads(lines[0])
        second = json.loads(lines[1])
        assert "ts" in first
        assert first["text"] == "bonjour"
        assert second["intent"] == "volume_up"
    finally:
        os.remove(path)
