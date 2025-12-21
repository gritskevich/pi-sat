import unittest
import os
import glob

class TestWakeWordListener(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.getenv("PISAT_RUN_WAKEWORD_TESTS", "0") != "1":
            raise unittest.SkipTest("Set PISAT_RUN_WAKEWORD_TESTS=1 to run wake word tests")

        try:
            from modules.wake_word_listener import WakeWordListener
        except ModuleNotFoundError as e:
            raise unittest.SkipTest(f"Wake word dependency not installed: {e}")

        try:
            cls.listener = WakeWordListener()
        except RuntimeError as e:
            raise unittest.SkipTest(str(e))
        try:
            from tests.test_utils import reset_model_state, process_audio_file
        except ModuleNotFoundError as e:
            raise unittest.SkipTest(f"Missing dependency for wake word tests: {e}")

        cls._reset_model_state = staticmethod(reset_model_state)
        cls._process_audio_file = staticmethod(process_audio_file)
    
    def test_listener_with_audio_files(self):
        audio_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio_samples", "wake_word")
        if not os.path.isdir(audio_dir):
            self.skipTest(f"Missing fixture directory: {audio_dir}")

        positive_files = glob.glob(os.path.join(audio_dir, "positive", "*.wav"))
        negative_files = glob.glob(os.path.join(audio_dir, "negative", "*.wav"))
        wav_files = [(path, True) for path in positive_files] + [(path, False) for path in negative_files]
        if not wav_files:
            self.skipTest(f"No .wav fixtures found in: {audio_dir}")

        for file, should_detect in wav_files:
            filename = os.path.basename(file)
            self._reset_model_state(self.listener.model)
            detected, max_confidence = self._process_audio_file(file, self.listener.model)

            self.assertEqual(
                detected,
                should_detect,
                f"File: {filename}, Expected: {should_detect}, Got: {detected}, Confidence: {max_confidence:.3f}",
            )

if __name__ == "__main__":
    unittest.main(verbosity=2) 
