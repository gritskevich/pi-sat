import unittest
import os
import glob

class TestWakeWord(unittest.TestCase):
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
    
    def test_alexa_files(self):
        audio_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio_samples")
        
        # Test positive wake word files
        positive_dir = os.path.join(audio_dir, "wake_word", "positive")
        positive_files = glob.glob(os.path.join(positive_dir, "*.wav"))
        if not positive_files:
            self.skipTest(f"No .wav fixtures found in: {positive_dir}")
        
        for file in positive_files:
            filename = os.path.basename(file)
            self._reset_model_state(self.listener.model)
            
            # Use the full path for process_audio_file
            detected, max_confidence = self._process_audio_file(file, self.listener.model)
            self.assertTrue(detected, 
                            f"File: {filename}, Expected: True, Got: {detected}, Confidence: {max_confidence:.3f}")
        
        # Test false positive files (should not trigger wake word)
        false_positive_files = [
            "false_digital_assistant.wav",
            "false_home_automation.wav", 
            "false_smart_speaker.wav",
            "false_voice_assistant.wav",
            "false_voice_control.wav"
        ]
        
        for filename in false_positive_files:
            file = os.path.join(audio_dir, "wake_word", "negative", filename)
            if os.path.exists(file):
                self._reset_model_state(self.listener.model)
                
                # Use the full path for process_audio_file
                detected, max_confidence = self._process_audio_file(file, self.listener.model)
                self.assertFalse(detected, 
                                f"File: {filename}, Expected: False, Got: {detected}, Confidence: {max_confidence:.3f}")

if __name__ == "__main__":
    unittest.main(verbosity=2) 
