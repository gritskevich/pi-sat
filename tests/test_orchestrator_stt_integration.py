import os
import unittest
from pathlib import Path

from tests.test_base import PiSatTestBase
from modules.logging_utils import log_success, log_warning
from modules.hailo_stt import HailoSTT


class TestOrchestratorSTTIntegration(PiSatTestBase):
    def setUp(self):
        if os.getenv("PISAT_RUN_HAILO_TESTS", "0") != "1":
            self.skipTest("Set PISAT_RUN_HAILO_TESTS=1 to run Hailo hardware tests")
        super().setUp()
        self.stt = HailoSTT(debug=True, language='fr')

    def tearDown(self):
        try:
            self.stt.cleanup()
        except Exception:
            pass
        super().tearDown()

    def _read_fixture_or_skip(self, relative_path: str) -> bytes:
        project_root = Path(__file__).resolve().parent.parent
        audio_path = project_root / relative_path
        if not audio_path.exists():
            self.skipTest(f"Missing audio fixture: {audio_path}")
        return audio_path.read_bytes()

    def _transcribe_or_skip(self, audio_bytes: bytes) -> str:
        if not self.stt.is_available():
            self.skipTest("Hailo STT not available")
        text = self.stt.transcribe(audio_bytes)
        self.assertIsInstance(text, str)
        return text

    def test_simple_command_transcription(self):
        audio = self._read_fixture_or_skip("tests/audio_samples/integration/fr/tu_peux_jouer_maman.wav")
        text = self._transcribe_or_skip(audio)
        if text.strip():
            log_success(self.logger, f"simple_command: {text!r}")
        else:
            log_warning(self.logger, "simple_command: empty transcription")

    def test_complex_command_transcription(self):
        audio = self._read_fixture_or_skip(
            "tests/audio_samples/integration/fr/alexa_pause_0.3s_tu_peux_jouer_maman.wav"
        )
        text = self._transcribe_or_skip(audio)
        if text.strip():
            log_success(self.logger, f"complex_command: {text!r}")
        else:
            log_warning(self.logger, "complex_command: empty transcription")

    def test_noise_only_transcription(self):
        audio = self._read_fixture_or_skip("tests/audio_samples/noise/noise.wav")
        text = self._transcribe_or_skip(audio)
        if text.strip():
            log_warning(self.logger, f"noise_only: non-empty transcription: {text!r}")
        else:
            log_success(self.logger, "noise_only: empty transcription (expected)")
    
    def test_empty_audio(self):
        """Test empty audio transcription"""
        text = self._transcribe_or_skip(b"")
        self.assertEqual(text, "", "Empty audio should return empty string")
        log_success(self.logger, f"empty_audio: '{text}' == ''")

if __name__ == "__main__":
    unittest.main(verbosity=2) 
