import json
import random
from pathlib import Path
import config
from .logging_utils import setup_logger, log_warning

logger = setup_logger(__name__)


class ResponseLibrary:
    def __init__(self, language: str = None, path: str = None):
        if language is None:
            if getattr(config, "STT_BACKEND", "hailo") == "cpu":
                language = getattr(config, "CPU_STT_LANGUAGE", "en")
            else:
                language = getattr(config, "LANGUAGE", "en")
        self.language = (language or "en").lower()
        self.path = Path(path or config.RESPONSE_LIBRARY_PATH)
        self._data = self._load()

    def _load(self):
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception as e:
            log_warning(logger, f"Response library load failed: {e}")
            return {}

    def get(self, key: str, fallback_key: str | None = None, **params) -> str | None:
        lang_bucket = self._data.get(self.language) or self._data.get("en") or {}
        options = lang_bucket.get(key)
        if not options and fallback_key:
            options = lang_bucket.get(fallback_key)
        if not options and key != "unknown":
            options = lang_bucket.get("unknown")
        if not options:
            return None
        template = random.choice(options)
        try:
            return template.format(**params)
        except KeyError:
            return template
