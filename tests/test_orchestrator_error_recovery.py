"""
Tests for orchestrator error recovery and retry logic.

Tests that orchestrator handles STT failures gracefully with retries.
"""

import unittest
import os
from unittest.mock import Mock, patch, MagicMock

from modules.orchestrator import Orchestrator
from modules.hailo_stt import HailoSTT
from tests.test_base import PiSatTestBase


class TestOrchestratorErrorRecovery(PiSatTestBase):
    """Test orchestrator error recovery for STT and other failures"""
    
    def setUp(self):
        if os.getenv("PISAT_RUN_LEGACY_ORCHESTRATOR_TESTS", "0") != "1":
            self.skipTest("Legacy orchestrator tests (set PISAT_RUN_LEGACY_ORCHESTRATOR_TESTS=1)")
        super().setUp()
        self.mock_mpd = Mock()
        self.orchestrator = Orchestrator(verbose=False, debug=True, mpd_controller=self.mock_mpd)
    
    def tearDown(self):
        if self.orchestrator:
            try:
                self.orchestrator.stop()
            except:
                pass
        super().tearDown()
    
    def test_orchestrator_retries_stt_on_transient_error(self):
        """Test: Orchestrator uses STT with retry logic
        
        Given: STT has retry logic built-in
        When: _transcribe_audio() called
        Then: STT retry logic handles transient errors
        """
        call_count = [0]
        
        def mock_transcribe_hailo(audio_data):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("Transient STT error")
            return "test transcription"
        
        self.orchestrator.stt._transcribe_hailo = mock_transcribe_hailo
        self.orchestrator.stt.is_available = Mock(return_value=True)
        HailoSTT._pipeline = MagicMock()  # Make pipeline available
        
        audio_data = b"fake audio data"
        result = self.orchestrator._transcribe_audio(audio_data)
        
        # STT retry logic should retry and succeed
        self.assertGreater(call_count[0], 1)
        self.assertEqual(result, "test transcription")
        self._add_result("orchestrator_stt_retry", True, "Orchestrator uses STT with retry logic")
    
    def test_orchestrator_handles_stt_unavailable(self):
        """Test: Orchestrator handles STT unavailable gracefully
        
        Given: STT is not available
        When: _transcribe_audio() called
        Then: Attempts reload and returns empty string
        """
        self.orchestrator.stt.is_available = Mock(return_value=False)
        self.orchestrator.stt.reload = Mock()
        
        audio_data = b"fake audio data"
        result = self.orchestrator._transcribe_audio(audio_data)
        
        self.orchestrator.stt.reload.assert_called_once()
        self.assertEqual(result, "")
        self._add_result("orchestrator_stt_unavailable", True, "Orchestrator handles STT unavailable")
    
    def test_orchestrator_notifies_user_on_transcription_failure(self):
        """Test: Orchestrator notifies user when transcription fails
        
        Given: Transcription returns empty string
        When: _process_command() called
        Then: User notified with error message
        """
        self.orchestrator._record_command = Mock(return_value=b"fake audio")
        self.orchestrator._transcribe_audio = Mock(return_value="")
        self.orchestrator.tts.speak = Mock()
        self.orchestrator.tts.get_response_template = Mock(return_value="Sorry, something went wrong")
        
        self.orchestrator._process_command()
        
        # Should call TTS with error message
        self.orchestrator.tts.speak.assert_called()
        call_args = self.orchestrator.tts.speak.call_args[0][0].lower()
        self.assertTrue("error" in call_args or "something went wrong" in call_args or "wrong" in call_args)
        self._add_result("orchestrator_notifies_user", True, "User notified on transcription failure")
    
    def test_orchestrator_handles_empty_audio(self):
        """Test: Orchestrator handles empty audio gracefully
        
        Given: Empty audio data
        When: _transcribe_audio() called
        Then: Returns empty string without retrying
        """
        result = self.orchestrator._transcribe_audio(b"")
        
        self.assertEqual(result, "")
        self._add_result("orchestrator_empty_audio", True, "Orchestrator handles empty audio")
    
    def test_orchestrator_restores_volume_on_error(self):
        """Test: Orchestrator restores volume even on error
        
        Given: Error occurs during processing
        When: _process_command() called
        Then: Volume restored in finally block
        """
        self.orchestrator.volume_manager.duck_music_volume = Mock()
        self.orchestrator.volume_manager.restore_music_volume = Mock()
        self.orchestrator._record_command = Mock(side_effect=Exception("Test error"))
        
        try:
            self.orchestrator._process_command()
        except:
            pass
        
        self.orchestrator.volume_manager.restore_music_volume.assert_called_once()
        self._add_result("orchestrator_restores_volume", True, "Volume restored on error")
    
    def test_orchestrator_handles_intent_classification_error(self):
        """Test: Orchestrator handles intent classification error
        
        Given: Intent classification raises exception
        When: _classify_intent() called
        Then: Returns None and logs error
        """
        self.orchestrator.intent_engine.classify = Mock(side_effect=Exception("Classification error"))
        
        result = self.orchestrator._classify_intent("test text")
        
        self.assertIsNone(result)
        self._add_result("orchestrator_intent_error", True, "Orchestrator handles intent classification error")
    
    def test_orchestrator_handles_intent_execution_error(self):
        """Test: Orchestrator handles intent execution error
        
        Given: Intent execution raises exception
        When: _execute_intent() called
        Then: Returns error response
        """
        mock_intent = Mock()
        mock_intent.intent_type = "play_music"
        mock_intent.parameters = {}
        
        self.orchestrator.mpd_controller.play = Mock(side_effect=Exception("MPD error"))
        self.orchestrator.tts.get_response_template = Mock(return_value="Sorry, something went wrong")
        
        result = self.orchestrator._execute_intent(mock_intent)
        
        self.assertIsNotNone(result)
        result_lower = result.lower()
        self.assertTrue("error" in result_lower or "something went wrong" in result_lower or "wrong" in result_lower)
        self._add_result("orchestrator_execution_error", True, "Orchestrator handles intent execution error")


if __name__ == "__main__":
    unittest.main(verbosity=2)
