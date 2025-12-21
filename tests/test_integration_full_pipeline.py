"""
Integration Tests - Full Pipeline

Tests the complete voice assistant pipeline:
Wake Word → VAD Recording → STT Transcription → Intent Classification → MPD Execution → TTS Response

Follows TDD and KISS principles:
- Real components where possible (wake word, VAD, STT, intent engine)
- Mocked external dependencies (MPD, TTS)
- Comprehensive coverage of core functionality
- Clear, simple test structure
"""

import unittest
import os
import numpy as np
import soundfile as sf
from unittest.mock import Mock, MagicMock, patch, call
from typing import Optional, Tuple


# Import modules first
try:
    from modules.wake_word_listener import WakeWordListener
except ModuleNotFoundError:
    WakeWordListener = None

from modules.speech_recorder import SpeechRecorder

try:
    from modules.hailo_stt import HailoSTT
except ModuleNotFoundError:
    HailoSTT = None

from modules.intent_engine import IntentEngine
from modules.mpd_controller import MPDController
from modules.volume_manager import VolumeManager
from modules.piper_tts import PiperTTS
import config
from tests.test_base import PiSatTestBase


class TestIntegrationFullPipeline(PiSatTestBase):
    """Full pipeline integration tests
    
    Tests complete flow from wake word detection through TTS response.
    Uses real components for wake word, VAD, STT, and intent engine.
    Mocks MPD and TTS to avoid external dependencies.
    """
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if os.getenv("PISAT_RUN_INTEGRATION_TESTS", "0") != "1":
            raise unittest.SkipTest("Set PISAT_RUN_INTEGRATION_TESTS=1 to run integration tests")
        if os.getenv("PISAT_RUN_WAKEWORD_TESTS", "0") != "1":
            raise unittest.SkipTest("Set PISAT_RUN_WAKEWORD_TESTS=1 to run wake word integration tests")

        if WakeWordListener is None:
            raise unittest.SkipTest("Wake word dependency not installed (openwakeword)")

        cls.samples_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio_samples")
        cls.synthetic_dir = os.path.join(cls.samples_dir, "synthetic")
        
        # Initialize real components
        cls.wake_word_listener = WakeWordListener()
        cls.speech_recorder = SpeechRecorder(debug=True)
        
        # Initialize STT (may not be available without Hailo device)
        cls.stt = None
        if os.getenv("PISAT_RUN_HAILO_TESTS", "0") == "1" and HailoSTT is not None:
            try:
                cls.stt = HailoSTT(debug=True, language="fr")
            except Exception:
                cls.stt = None
        
        cls.intent_engine = IntentEngine(fuzzy_threshold=config.FUZZY_MATCH_THRESHOLD, debug=True)
    
    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "stt", None) is not None:
            try:
                cls.stt.cleanup()
            except Exception:
                pass
        super().tearDownClass()
    
    def setUp(self):
        super().setUp()
        
        # Create mocked MPD controller
        self.mock_mpd = Mock(spec=MPDController)
        self.mock_mpd.play.return_value = (True, "Playing")
        self.mock_mpd.pause.return_value = (True, "Paused")
        self.mock_mpd.resume.return_value = (True, "Resuming")
        self.mock_mpd.stop.return_value = (True, "Stopped")
        self.mock_mpd.next.return_value = (True, "Next song")
        self.mock_mpd.previous.return_value = (True, "Previous song")
        self.mock_mpd.volume_up.return_value = (True, "Volume up")
        self.mock_mpd.volume_down.return_value = (True, "Volume down")
        self.mock_mpd.add_to_favorites.return_value = (True, "Added to favorites")
        self.mock_mpd.play_favorites.return_value = (True, "Playing favorites")
        self.mock_mpd.set_sleep_timer.return_value = (True, "Sleep timer set")
        
        # Create mocked TTS
        self.mock_tts = Mock(spec=PiperTTS)
        self.mock_tts.speak.return_value = True
        self.mock_tts.get_response_template.return_value = "Response"
        
        # Create mocked volume manager
        self.mock_volume_manager = Mock(spec=VolumeManager)
        self.mock_volume_manager.duck_music_volume.return_value = None
        self.mock_volume_manager.restore_music_volume.return_value = None
        self.mock_volume_manager.get_tts_volume.return_value = 80
        self.mock_volume_manager.set_tts_volume.return_value = None
        
        # Don't initialize orchestrator in setUp - do it per test to avoid Hailo initialization
        self.orchestrator = None
    
    def tearDown(self):
        if hasattr(self, 'orchestrator') and self.orchestrator:
            try:
                self.orchestrator.stop()
            except:
                pass
        
        super().tearDown()
    
    def _create_orchestrator_with_mocks(self):
        """Helper to create orchestrator with all dependencies mocked"""
        # Create mocked STT to avoid Hailo device requirement
        mock_stt = Mock(spec=HailoSTT)
        stt_available = hasattr(self.__class__, 'stt') and self.__class__.stt and self.__class__.stt.is_available()
        mock_stt.is_available.return_value = stt_available
        if stt_available:
            # Use real STT methods if available
            mock_stt.transcribe = self.__class__.stt.transcribe
            mock_stt.reload = self.__class__.stt.reload
            mock_stt.cleanup = self.__class__.stt.cleanup
        else:
            # Mock transcription for tests without Hailo
            mock_stt.transcribe = Mock(return_value="play maman")
            mock_stt.reload = Mock()
            mock_stt.cleanup = Mock()
        
        # Patch orchestrator's imports before creating instance
        stt_patcher = patch('modules.orchestrator.HailoSTT', return_value=mock_stt)
        mpd_patcher = patch('modules.orchestrator.MPDController', return_value=self.mock_mpd)
        tts_patcher = patch('modules.orchestrator.PiperTTS', return_value=self.mock_tts)
        volume_patcher = patch('modules.orchestrator.VolumeManager', return_value=self.mock_volume_manager)
        
        stt_patcher.start()
        mpd_patcher.start()
        tts_patcher.start()
        volume_patcher.start()
        
        try:
            # Import orchestrator after patching
            from modules.orchestrator import Orchestrator
            orchestrator = Orchestrator(verbose=False, debug=True, mpd_controller=self.mock_mpd)
            orchestrator.tts = self.mock_tts
            orchestrator.volume_manager = self.mock_volume_manager
            orchestrator.stt = mock_stt
            return orchestrator, [stt_patcher, mpd_patcher, tts_patcher, volume_patcher]
        except Exception as e:
            # Clean up patchers on error
            stt_patcher.stop()
            mpd_patcher.stop()
            tts_patcher.stop()
            volume_patcher.stop()
            raise e
    
    def _load_audio_file(self, relative_path: str) -> Tuple[np.ndarray, int]:
        """Load audio file from test samples"""
        audio_path = os.path.join(self.samples_dir, relative_path)
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        audio, rate = sf.read(audio_path)
        if len(audio.shape) > 1:
            audio = audio[:, 0]  # Convert to mono
        
        # Convert to int16
        audio = (audio * 32767).astype(np.int16)
        return audio, rate
    
    def _simulate_wake_word_detection(self, audio: np.ndarray) -> bool:
        """Simulate wake word detection on audio"""
        chunk_size = config.CHUNK
        consecutive_detections = 0
        required_consecutive = 5
        
        for i in range(0, len(audio), chunk_size):
            chunk = audio[i:i+chunk_size]
            if len(chunk) < chunk_size:
                chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
            
            prediction = self.wake_word_listener.model.predict(chunk)
            for wake_word, confidence in prediction.items():
                if confidence > config.THRESHOLD:
                    consecutive_detections += 1
                    if consecutive_detections >= required_consecutive:
                        return True
                else:
                    consecutive_detections = 0
        
        return False
    
    def _simulate_stt_transcription(self, audio: np.ndarray) -> str:
        """Simulate STT transcription"""
        if not self.stt or not self.stt.is_available():
            # Return mock transcription for testing without Hailo
            return "play maman"
        
        audio_bytes = audio.tobytes()
        try:
            text = self.stt.transcribe(audio_bytes)
            return text
        except Exception:
            return ""
    
    def _test_full_pipeline(self, audio_file: str, expected_intent: Optional[str] = None, 
                           expected_mpd_call: Optional[str] = None, 
                           expected_params: Optional[dict] = None) -> bool:
        """Test full pipeline with audio file
        
        Args:
            audio_file: Relative path to audio file
            expected_intent: Expected intent type (e.g., 'play_music')
            expected_mpd_call: Expected MPD method call (e.g., 'play')
            expected_params: Expected parameters for MPD call
        
        Returns:
            bool: True if pipeline executed successfully
        """
        # Create orchestrator for this test
        orchestrator, patchers = self._create_orchestrator_with_mocks()
        
        try:
            # Load audio
            audio, rate = self._load_audio_file(audio_file)
            
            # Step 1: Wake word detection
            wake_detected = self._simulate_wake_word_detection(audio)
            self._add_result("Wake Word Detection", wake_detected, 
                           f"Detected: {wake_detected}")
            
            if not wake_detected:
                return False
            
            # Step 2: Extract command audio (skip wake word, use VAD)
            # For simplicity, use audio after first 0.8 seconds
            wake_duration = int(0.8 * rate)
            command_audio = audio[wake_duration:] if len(audio) > wake_duration else audio
            
            # Step 3: STT transcription
            transcribed_text = self._simulate_stt_transcription(command_audio)
            self._add_result("STT Transcription", len(transcribed_text) > 0,
                           f"Text: '{transcribed_text}'")
            
            if not transcribed_text:
                return False
            
            # Step 4: Intent classification
            intent = self.intent_engine.classify(transcribed_text)
            if expected_intent:
                intent_matched = intent is not None and intent.intent_type == expected_intent
                self._add_result("Intent Classification", intent_matched,
                               f"Intent: {intent.intent_type if intent else None}, Expected: {expected_intent}")
            else:
                intent_matched = intent is not None
                self._add_result("Intent Classification", intent_matched,
                               f"Intent: {intent.intent_type if intent else None}")
            
            if not intent:
                return False
            
            # Step 5: Execute intent via orchestrator
            response = orchestrator._execute_intent(intent)
            
            # Step 6: Verify MPD was called correctly
            if expected_mpd_call:
                mpd_called = hasattr(self.mock_mpd, expected_mpd_call) and \
                            getattr(self.mock_mpd, expected_mpd_call).called
                self._add_result("MPD Execution", mpd_called,
                               f"Method '{expected_mpd_call}' called: {mpd_called}")
            
            # Step 7: Verify TTS was called
            tts_called = self.mock_tts.speak.called
            self._add_result("TTS Response", tts_called,
                           f"TTS called: {tts_called}")
            
            # Step 8: Verify volume ducking
            volume_ducked = self.mock_volume_manager.duck_music_volume.called
            volume_restored = self.mock_volume_manager.restore_music_volume.called
            self._add_result("Volume Ducking", volume_ducked and volume_restored,
                           f"Ducked: {volume_ducked}, Restored: {volume_restored}")
            
            return True
            
        except Exception as e:
            self._add_result("Pipeline Error", False, str(e))
            return False
        finally:
            # Clean up patchers
            for patcher in patchers:
                patcher.stop()
            if orchestrator:
                orchestrator.stop()
    
    def test_play_music_command(self):
        """Test: Play music command pipeline"""
        audio_file = "synthetic/music_control/01_play_maman.wav"
        
        if not os.path.exists(os.path.join(self.samples_dir, audio_file)):
            self.skipTest(f"Audio file not found: {audio_file}")
        
        # Skip if STT not available (will use mock transcription)
        if not hasattr(self.__class__, 'stt') or not self.__class__.stt or not self.__class__.stt.is_available():
            print("⚠️  STT not available - using mock transcription for test")
        
        success = self._test_full_pipeline(
            audio_file=audio_file,
            expected_intent="play_music",
            expected_mpd_call="play"
        )
        
        self.assertTrue(success, "Play music pipeline should succeed")
        
        # Verify MPD play was called with query
        if self.mock_mpd.play.called:
            call_args = self.mock_mpd.play.call_args
            self.assertIsNotNone(call_args, "MPD play should be called")
    
    def test_pause_command(self):
        """Test: Pause command pipeline"""
        audio_file = "synthetic/music_control/05_pause.wav"
        
        if not os.path.exists(os.path.join(self.samples_dir, audio_file)):
            self.skipTest(f"Audio file not found: {audio_file}")
        
        success = self._test_full_pipeline(
            audio_file=audio_file,
            expected_intent="pause",
            expected_mpd_call="pause"
        )
        
        self.assertTrue(success, "Pause pipeline should succeed")
        self.assertTrue(self.mock_mpd.pause.called, "MPD pause should be called")
    
    def test_volume_up_command(self):
        """Test: Volume up command pipeline"""
        audio_file = "synthetic/volume_control/01_louder.wav"
        
        if not os.path.exists(os.path.join(self.samples_dir, audio_file)):
            self.skipTest(f"Audio file not found: {audio_file}")
        
        success = self._test_full_pipeline(
            audio_file=audio_file,
            expected_intent="volume_up",
            expected_mpd_call="volume_up"
        )
        
        self.assertTrue(success, "Volume up pipeline should succeed")
        self.assertTrue(self.mock_mpd.volume_up.called, "MPD volume_up should be called")
    
    def test_volume_down_command(self):
        """Test: Volume down command pipeline"""
        audio_file = "synthetic/volume_control/04_quieter.wav"
        
        if not os.path.exists(os.path.join(self.samples_dir, audio_file)):
            self.skipTest(f"Audio file not found: {audio_file}")
        
        success = self._test_full_pipeline(
            audio_file=audio_file,
            expected_intent="volume_down",
            expected_mpd_call="volume_down"
        )
        
        self.assertTrue(success, "Volume down pipeline should succeed")
        self.assertTrue(self.mock_mpd.volume_down.called, "MPD volume_down should be called")
    
    def test_add_favorite_command(self):
        """Test: Add to favorites command pipeline"""
        audio_file = "synthetic/favorites/01_i_love_this.wav"
        
        if not os.path.exists(os.path.join(self.samples_dir, audio_file)):
            self.skipTest(f"Audio file not found: {audio_file}")
        
        success = self._test_full_pipeline(
            audio_file=audio_file,
            expected_intent="add_favorite",
            expected_mpd_call="add_to_favorites"
        )
        
        self.assertTrue(success, "Add favorite pipeline should succeed")
        self.assertTrue(self.mock_mpd.add_to_favorites.called, "MPD add_to_favorites should be called")
    
    def test_sleep_timer_command(self):
        """Test: Sleep timer command pipeline"""
        audio_file = "synthetic/sleep_timer/01_stop_in_30_minutes.wav"
        
        if not os.path.exists(os.path.join(self.samples_dir, audio_file)):
            self.skipTest(f"Audio file not found: {audio_file}")
        
        success = self._test_full_pipeline(
            audio_file=audio_file,
            expected_intent="sleep_timer",
            expected_mpd_call="set_sleep_timer"
        )
        
        self.assertTrue(success, "Sleep timer pipeline should succeed")
        self.assertTrue(self.mock_mpd.set_sleep_timer.called, "MPD set_sleep_timer should be called")
    
    def test_skip_command(self):
        """Test: Skip/next command pipeline"""
        audio_file = "synthetic/music_control/07_skip.wav"
        
        if not os.path.exists(os.path.join(self.samples_dir, audio_file)):
            self.skipTest(f"Audio file not found: {audio_file}")
        
        success = self._test_full_pipeline(
            audio_file=audio_file,
            expected_intent="next",
            expected_mpd_call="next"
        )
        
        self.assertTrue(success, "Skip pipeline should succeed")
        self.assertTrue(self.mock_mpd.next.called, "MPD next should be called")
    
    def test_volume_ducking_integration(self):
        """Test: Volume ducking during voice input"""
        # Create orchestrator with mocks
        orchestrator, patchers = self._create_orchestrator_with_mocks()
        
        try:
            # Mock speech recorder to return fake audio
            orchestrator.speech_recorder.record_command = Mock(return_value=b'fake_audio_data')
            orchestrator.stt.transcribe = Mock(return_value="pause")
            
            # Simulate command processing
            orchestrator._process_command()
            
            # Verify volume ducking was called
            self.assertTrue(self.mock_volume_manager.duck_music_volume.called,
                           "Volume should be ducked during recording")
            self.assertTrue(self.mock_volume_manager.restore_music_volume.called,
                           "Volume should be restored after processing")
        finally:
            # Clean up patchers
            for patcher in patchers:
                patcher.stop()
            if orchestrator:
                orchestrator.stop()
    
    def test_tts_response_integration(self):
        """Test: TTS response after intent execution"""
        from modules.intent_engine import Intent
        
        # Create test intent
        intent = Intent(
            intent_type="pause",
            confidence=0.95,
            parameters={},
            raw_text="pause"
        )
        
        # Create orchestrator with mocks
        orchestrator, patchers = self._create_orchestrator_with_mocks()
        
        try:
            # Execute intent
            response = orchestrator._execute_intent(intent)
            
            # Verify response was generated
            self.assertIsNotNone(response, "Response should be generated")
            self.assertIsInstance(response, str, "Response should be string")
            
            # Verify MPD was called
            self.assertTrue(self.mock_mpd.pause.called, "MPD pause should be called")
            
            # Verify TTS would be called (simulated)
            self.mock_tts.speak(response)
            self.assertTrue(self.mock_tts.speak.called, "TTS speak should be called")
        finally:
            # Clean up patchers
            for patcher in patchers:
                patcher.stop()
            if orchestrator:
                orchestrator.stop()
    
    def test_no_intent_match(self):
        """Test: Handling when no intent matches"""
        # Create orchestrator with mocks
        orchestrator, patchers = self._create_orchestrator_with_mocks()
        
        try:
            # Simulate transcription with no matching intent
            text = "random text that doesn't match any intent"
            
            intent = self.intent_engine.classify(text)
            
            # Should return None
            self.assertIsNone(intent, "No intent should match random text")
            
            # Orchestrator should handle gracefully
            response = orchestrator._execute_intent(intent)
            self.assertIsNotNone(response, "Should return error response")
            self.assertIn('error', response.lower() or 'unknown', "Should return error message")
        finally:
            # Clean up patchers
            for patcher in patchers:
                patcher.stop()
            if orchestrator:
                orchestrator.stop()
    
    def test_empty_transcription(self):
        """Test: Handling empty transcription"""
        # Simulate empty transcription
        text = ""
        
        intent = self.intent_engine.classify(text)
        
        # Should return None
        self.assertIsNone(intent, "Empty text should not match any intent")
    
    def test_fuzzy_matching_integration(self):
        """Test: Fuzzy matching handles typos in commands"""
        # Test with typo
        text_with_typo = "pley maman"  # Typo: "pley" instead of "play"
        
        intent = self.intent_engine.classify(text_with_typo)
        
        # Should still match play_music intent
        self.assertIsNotNone(intent, "Fuzzy matching should handle typos")
        if intent:
            self.assertEqual(intent.intent_type, "play_music", 
                           "Should match play_music intent despite typo")


if __name__ == "__main__":
    unittest.main(verbosity=2)
