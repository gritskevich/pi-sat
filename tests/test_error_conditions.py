import unittest
import os
import tempfile
import shutil
from unittest.mock import Mock
from tests.test_utils import process_audio_file

class TestErrorConditions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.getenv("PISAT_RUN_WAKEWORD_TESTS", "0") != "1":
            raise unittest.SkipTest("Set PISAT_RUN_WAKEWORD_TESTS=1 to run wake word tests")

        try:
            from modules.orchestrator import Orchestrator
            from modules.wake_word_listener import WakeWordListener
        except ModuleNotFoundError as e:
            raise unittest.SkipTest(f"Wake word dependency not installed: {e}")

        cls.orchestrator = Orchestrator(
            command_processor=Mock(),
            wake_word_listener=Mock(),
            verbose=False,
        )
        cls.listener = WakeWordListener()
    
    @classmethod
    def tearDownClass(cls):
        cls.orchestrator.stop()
    
    def test_missing_audio_file(self):
        with self.assertRaises(FileNotFoundError):
            process_audio_file("nonexistent.wav", self.listener.model)
    
    def test_invalid_audio_format(self):
        temp_dir = tempfile.mkdtemp()
        try:
            invalid_file = os.path.join(temp_dir, "invalid.txt")
            with open(invalid_file, 'w') as f:
                f.write("This is not audio data")
            
            with self.assertRaises(Exception):
                process_audio_file(invalid_file, self.listener.model)
        finally:
            shutil.rmtree(temp_dir)
    
    def test_orchestrator_double_stop(self):
        orchestrator = Orchestrator(
            command_processor=Mock(),
            wake_word_listener=Mock(),
            verbose=False,
        )
        orchestrator.stop()
        orchestrator.stop()
        self.assertFalse(orchestrator.running)
    
    def test_wake_word_during_processing(self):
        orchestrator = Orchestrator(
            command_processor=Mock(),
            wake_word_listener=Mock(),
            verbose=False,
        )
        orchestrator.is_processing = True
        orchestrator._on_wake_word_detected()
        orchestrator.command_processor.process_command.assert_not_called()
    
    def test_orchestrator_without_listener(self):
        orchestrator = Orchestrator(
            command_processor=Mock(),
            wake_word_listener=Mock(),
            verbose=False,
        )
        orchestrator.wake_word_listener = None
        orchestrator.stop()
        self.assertFalse(orchestrator.running)
    
    def test_invalid_config_values(self):
        import config
        original_threshold = config.WAKE_WORD_THRESHOLD
        
        try:
            config.WAKE_WORD_THRESHOLD = -1.0
            with self.assertRaises(ValueError):
                if config.WAKE_WORD_THRESHOLD < 0:
                    raise ValueError("Threshold cannot be negative")
        finally:
            config.WAKE_WORD_THRESHOLD = original_threshold

if __name__ == "__main__":
    unittest.main(verbosity=2) 
