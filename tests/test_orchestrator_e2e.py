import os
import unittest

from modules.command_processor import CommandProcessor
from modules.hailo_stt import HailoSTT
from modules.intent_engine import IntentEngine
from tests.test_base import PiSatTestBase


class TestOrchestratorE2E(PiSatTestBase):
    """
    End-to-end-ish test for the command pipeline using generated audio fixtures.

    Scope: WAV → Hailo STT → Intent Engine → MPD/TTS (mocked) → success.
    Wake word detection is tested separately (openWakeWord is not reliable on TTS audio).
    """

    class _FakeSpeechRecorder:
        def __init__(self, audio_bytes: bytes):
            self._audio_bytes = audio_bytes

        def record_command(self):
            return self._audio_bytes

        def record_from_stream(self, stream=None, input_rate=None, skip_initial_seconds=0.0):
            return self._audio_bytes

    class _FakeVolumeManager:
        def duck_music_volume(self, duck_to=20):
            return True

        def restore_music_volume(self):
            return True

    class _FakeTTS:
        def get_response_template(self, template_name: str, **kwargs):
            return template_name

        def speak(self, text: str):
            return True

    class _FakeMPD:
        def play(self, query):
            return True, "ok", 1.0

        def play_favorites(self):
            return True, "ok"

        def pause(self):
            return True, "ok"

        def resume(self):
            return True, "ok"

        def stop(self):
            return True, "ok"

        def next(self):
            return True, "ok"

        def previous(self):
            return True, "ok"

        def volume_up(self, step):
            return True, "ok"

        def volume_down(self, step):
            return True, "ok"

        def add_to_favorites(self):
            return True, "ok"

        def set_sleep_timer(self, minutes):
            return True, "ok"

        def set_repeat(self, mode):
            return True, "ok"

        def set_shuffle(self, enabled):
            return True, "ok"

        def add_to_queue(self, query, play_next=False):
            return True, "ok"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if os.getenv("PISAT_RUN_HAILO_TESTS", "0") != "1":
            raise unittest.SkipTest("Set PISAT_RUN_HAILO_TESTS=1 to run Hailo hardware tests")

        cls.fixtures_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "audio_samples",
            "integration",
            "fr",
        )

        if not os.path.exists(cls.fixtures_dir):
            raise unittest.SkipTest(
                "Generated FR suite not found (run: python scripts/generate_music_test_audio.py --languages fr)"
            )

        cls.stt = HailoSTT(debug=True, language="fr")
        if not cls.stt.is_available():
            raise unittest.SkipTest("Hailo STT not available")

        cls.intent_engine = IntentEngine(debug=True, language="fr")

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "stt"):
            cls.stt.cleanup()
        super().tearDownClass()

    def _run_case(self, filename: str):
        audio_path = os.path.join(self.fixtures_dir, filename)
        if not os.path.exists(audio_path):
            self.skipTest(f"Missing audio fixture: {audio_path}")

        with open(audio_path, "rb") as f:
            audio_bytes = f.read()

        processor = CommandProcessor(
            speech_recorder=self._FakeSpeechRecorder(audio_bytes),
            stt_engine=self.stt,
            intent_engine=self.intent_engine,
            mpd_controller=self._FakeMPD(),
            tts_engine=self._FakeTTS(),
            volume_manager=self._FakeVolumeManager(),
            debug=True,
            verbose=False,
        )

        ok = processor.process_command()
        self.assertTrue(ok, f"CommandProcessor failed for {filename}")

        text = processor._transcribe_audio(audio_bytes)
        self.assertTrue(bool(text and text.strip()), f"Empty transcription for {filename}")

        intent = processor._classify_intent(text)
        self.assertIsNotNone(intent, f"No intent for {filename} (text: {text!r})")

    def test_e2e_music_commands_fr(self):
        cases = [
            "pause.wav",
            "suivant.wav",
            "alexa_pause_0.3s_mid_pause_0.8s_arrete_dans_30_minutes.wav",
        ]
        for filename in cases:
            with self.subTest(filename=filename):
                self._run_case(filename)


if __name__ == "__main__":
    unittest.main(verbosity=2)
