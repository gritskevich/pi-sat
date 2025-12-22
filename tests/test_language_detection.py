"""
Hailo STT - French-first language forcing tests (hardware).

Uses the centralized metadata registry + ElevenLabs E2E French suite.
"""

import json
import os
import unittest
import wave
from pathlib import Path

import numpy as np

from modules.hailo_stt import HailoSTT


PROJECT_ROOT = Path(__file__).resolve().parent.parent
METADATA_PATH = PROJECT_ROOT / "tests" / "audio_samples" / "test_metadata.json"
SUITE_ID = "e2e_french"


def _load_suite_or_skip() -> dict:
    if not METADATA_PATH.exists():
        raise unittest.SkipTest(f"Missing metadata: {METADATA_PATH}")

    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    suite = metadata.get("suites", {}).get(SUITE_ID)
    if not suite:
        raise unittest.SkipTest(f"Missing suite: {SUITE_ID}")
    return suite


def _load_command_bytes(wav_path: Path, command_start_s: float) -> bytes:
    with wave.open(str(wav_path), "rb") as wf:
        rate = wf.getframerate()
        raw = wf.readframes(wf.getnframes())
    audio_i16 = np.frombuffer(raw, dtype=np.int16)
    start = int(command_start_s * rate)
    if start >= audio_i16.size:
        return b""
    return audio_i16[start:].tobytes()


class TestLanguageDetectionFR(unittest.TestCase):
    """Validate that French forcing is applied and works on a known French command."""

    @classmethod
    def setUpClass(cls):
        if os.getenv("PISAT_RUN_HAILO_TESTS", "0") != "1":
            raise unittest.SkipTest("Set PISAT_RUN_HAILO_TESTS=1 to run Hailo hardware tests")

        cls.suite = _load_suite_or_skip()
        cls.case = cls.suite["tests"]["positive"][0]
        cls.wav_path = PROJECT_ROOT / cls.case["file"]
        if not cls.wav_path.exists():
            raise unittest.SkipTest(f"Missing generated audio: {cls.wav_path} (run scripts/generate_e2e_french_tests.py)")

        cls.command_start_s = float(cls.case.get("command_start_s", cls.suite["structure"]["command_start_s"]))
        cls.query = (cls.case.get("parameters") or {}).get("query")

    def test_forced_language_is_fr(self):
        stt = HailoSTT(debug=True, language="fr")
        try:
            if not stt.is_available():
                self.skipTest("Hailo STT not available")
            self.assertEqual(stt.get_language(), "fr")
        finally:
            stt.cleanup()

    def test_transcribe_known_french_command(self):
        stt = HailoSTT(debug=True, language="fr")
        try:
            if not stt.is_available():
                self.skipTest("Hailo STT not available")

            audio_bytes = _load_command_bytes(self.wav_path, self.command_start_s)
            self.assertGreater(len(audio_bytes), 0)

            text = stt.transcribe(audio_bytes)
            self.assertIsInstance(text, str)
            self.assertTrue(text.strip(), "Empty transcription")

            if self.query:
                self.assertIn(self.query.lower(), text.lower())
        finally:
            stt.cleanup()

    def test_language_param_overrides_env(self):
        prev = os.environ.get("HAILO_STT_LANGUAGE")
        os.environ["HAILO_STT_LANGUAGE"] = "en"
        try:
            stt = HailoSTT(debug=True, language="fr")
            try:
                if not stt.is_available():
                    self.skipTest("Hailo STT not available")
                self.assertEqual(stt.get_language(), "fr")
            finally:
                stt.cleanup()
        finally:
            if prev is None:
                os.environ.pop("HAILO_STT_LANGUAGE", None)
            else:
                os.environ["HAILO_STT_LANGUAGE"] = prev


if __name__ == "__main__":
    unittest.main(verbosity=2)

