import os
import unittest
from pathlib import Path

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
        audio = self._read_fixture_or_skip("tests/audio_samples/integration/fr/tu_peux_jouer_maman.wav")
        text = self.stt.transcribe(audio)
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
