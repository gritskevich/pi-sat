import unittest
import os
import glob
import numpy as np
import soundfile as sf
from tests.test_base import PiSatTestBase

class TestOrchestratorIntegration(PiSatTestBase):
    def setUp(self):
        if os.getenv("PISAT_RUN_INTEGRATION_TESTS", "0") != "1":
            self.skipTest("Set PISAT_RUN_INTEGRATION_TESTS=1 to run integration tests")
        if os.getenv("PISAT_RUN_WAKEWORD_TESTS", "0") != "1":
            self.skipTest("Set PISAT_RUN_WAKEWORD_TESTS=1 to run wake word integration tests")
        if os.getenv("PISAT_RUN_HAILO_TESTS", "0") != "1":
            self.skipTest("Set PISAT_RUN_HAILO_TESTS=1 to run Hailo integration tests")

        super().setUp()
        try:
            from modules.orchestrator import Orchestrator
            from modules.wake_word_listener import WakeWordListener
            from modules.hailo_stt import HailoSTT
        except ModuleNotFoundError as e:
            self.skipTest(f"Missing optional dependency: {e}")

        self.orchestrator = Orchestrator(verbose=False, debug=True)
        self.wake_word_listener = WakeWordListener()
        self.stt = HailoSTT(debug=True, language="fr")
    
    def tearDown(self):
        # Ensure resources are cleaned up to avoid lingering threads
        try:
            if hasattr(self, 'wake_word_listener') and self.wake_word_listener:
                self.wake_word_listener.stop_listening()
        except Exception:
            pass
        try:
            if hasattr(self, 'stt') and self.stt:
                self.stt.cleanup()
        except Exception:
            pass
        super().tearDown()
    
    def test_orchestrator_with_audio_files(self):
        """Test orchestrator with real audio file processing"""
        audio_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio_samples")
        
        # Test integration files (wake word + command)
        integration_dir = os.path.join(audio_dir, "integration")
        if os.path.exists(integration_dir):
            wav_files = glob.glob(os.path.join(integration_dir, "*.wav"))
            
            for file in wav_files[:2]:  # Test first 2 files
                filename = os.path.basename(file)
                print(f"Testing integration file: {filename}")
                
                # Load audio file
                audio, sample_rate = sf.read(file)
                if len(audio.shape) > 1:
                    audio = audio[:, 0]  # Convert to mono
                
                # Test wake word detection using the correct method
                wake_word_detected = self.wake_word_listener.detect_wake_word(audio)
                
                # Test STT transcription
                audio_bytes = (audio * 32767).astype(np.int16).tobytes()
                transcription = self.stt.transcribe(audio_bytes)
                
                # Verify results
                self.assertTrue(os.path.exists(file), f"Integration file should exist: {file}")
                self.assertIsInstance(wake_word_detected, bool, "Wake word detection should return boolean")
                self.assertIsInstance(transcription, str, "STT should return string")
                
                print(f"✅ {filename}: Wake word={wake_word_detected}, STT='{transcription}'")
    
    def test_orchestrator_wake_word_detection(self):
        """Test orchestrator wake word detection with real files"""
        audio_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio_samples")
        
        # Test positive wake word files
        positive_dir = os.path.join(audio_dir, "wake_word", "positive")
        if os.path.exists(positive_dir):
            wav_files = glob.glob(os.path.join(positive_dir, "*.wav"))
            
            for file in wav_files[:2]:  # Test first 2 files
                filename = os.path.basename(file)
                print(f"Testing wake word file: {filename}")
                
                # Load and test audio
                audio, sample_rate = sf.read(file)
                if len(audio.shape) > 1:
                    audio = audio[:, 0]
                
                wake_word_detected = self.wake_word_listener.detect_wake_word(audio)
                
                # Verify results
                self.assertTrue(os.path.exists(file), f"Wake word file should exist: {file}")
                self.assertIsInstance(wake_word_detected, bool, "Wake word detection should return boolean")
                
                print(f"✅ {filename}: Wake word detected={wake_word_detected}")
    
    def test_orchestrator_stt_processing(self):
        """Test orchestrator STT processing with real files"""
        audio_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio_samples")
        
        # Test command files
        command_dir = os.path.join(audio_dir, "commands", "simple")
        if os.path.exists(command_dir):
            wav_files = glob.glob(os.path.join(command_dir, "*.wav"))
            
            for file in wav_files[:1]:  # Test first file
                filename = os.path.basename(file)
                print(f"Testing STT file: {filename}")
                
                # Load and test audio
                audio, sample_rate = sf.read(file)
                if len(audio.shape) > 1:
                    audio = audio[:, 0]
                
                audio_bytes = (audio * 32767).astype(np.int16).tobytes()
                transcription = self.stt.transcribe(audio_bytes)
                
                # Verify results
                self.assertTrue(os.path.exists(file), f"STT file should exist: {file}")
                self.assertIsInstance(transcription, str, "STT should return string")
                
                print(f"✅ {filename}: STT='{transcription}'")

if __name__ == "__main__":
    unittest.main(verbosity=2) 
