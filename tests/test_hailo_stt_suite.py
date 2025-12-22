import os
import unittest
import json
import wave
from pathlib import Path

import numpy as np

from modules.hailo_stt import HailoSTT
from tests.test_base import PiSatTestBase


class TestHailoSTTSuite(PiSatTestBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if os.getenv("PISAT_RUN_HAILO_TESTS", "0") != "1":
            raise unittest.SkipTest("Set PISAT_RUN_HAILO_TESTS=1 to run Hailo hardware tests")

        cls.project_root = Path(__file__).resolve().parent.parent
        cls.stt = HailoSTT(debug=True, language="fr")
        if not cls.stt.is_available():
            raise unittest.SkipTest("Hailo STT not available")

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "stt", None) is not None:
            try:
                cls.stt.cleanup()
            except Exception:
                pass
        super().tearDownClass()

    def _read_fixture_or_skip(self, relative_path: str) -> bytes:
        audio_path = self.project_root / relative_path
        if not audio_path.exists():
            self.skipTest(f"Missing audio fixture: {audio_path}")
        return audio_path.read_bytes()

    def test_transcribe_simple_fixture(self):
        metadata_path = self.project_root / "tests" / "audio_samples" / "test_metadata.json"
        if not metadata_path.exists():
            self.skipTest(f"Missing metadata: {metadata_path}")

        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        suite = metadata.get("suites", {}).get("e2e_french")
        if not suite:
            self.skipTest("Missing suite: e2e_french")

        case = suite["tests"]["positive"][0]
        wav_path = self.project_root / case["file"]
        if not wav_path.exists():
            self.skipTest(f"Missing generated audio: {wav_path} (run scripts/generate_e2e_french_tests.py)")

        # Extract command using metadata and transcribe only the command portion.
        command_start_s = float(case.get("command_start_s", suite["structure"]["command_start_s"]))
        with wave.open(str(wav_path), "rb") as wf:
            rate = wf.getframerate()
            samples = wf.readframes(wf.getnframes())
        audio_i16 = np.frombuffer(samples, dtype=np.int16)
        start = int(command_start_s * rate)
        command_i16 = audio_i16[start:]
        text = self.stt.transcribe(command_i16.tobytes())
        self.assertIsInstance(text, str)

    def test_transcribe_noise_fixture(self):
        audio = self._read_fixture_or_skip("tests/audio_samples/noise/noise.wav")
        text = self.stt.transcribe(audio)
        self.assertIsInstance(text, str)

    def test_transcribe_empty_audio(self):
        text = self.stt.transcribe(b"")
        self.assertEqual(text, "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
