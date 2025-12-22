"""
Test TTS Integration in Orchestrator

Tests that TTS is properly integrated and called in the orchestrator pipeline.
Follows TDD approach - comprehensive tests for TTS functionality.
"""

import unittest
import os
from unittest.mock import Mock, MagicMock, patch, call
from pathlib import Path

from modules.orchestrator import Orchestrator
from modules.intent_engine import Intent, IntentEngine
from modules.mpd_controller import MPDController
from modules.piper_tts import PiperTTS
import config


class TestTTSIntegration(unittest.TestCase):
    """Test TTS integration in orchestrator"""

    def setUp(self):
        """Set up test fixtures"""
        if os.getenv("PISAT_RUN_LEGACY_ORCHESTRATOR_TESTS", "0") != "1":
            self.skipTest("Legacy orchestrator tests (set PISAT_RUN_LEGACY_ORCHESTRATOR_TESTS=1)")

        # Mock MPD controller
        self.mock_mpd = Mock(spec=MPDController)
        self.mock_mpd.play.return_value = (True, "Playing maman")
        self.mock_mpd.pause.return_value = (True, "Paused")
        
        # Create orchestrator with mocks
        with patch('modules.orchestrator.VolumeManager'), \
             patch('modules.orchestrator.WakeWordListener'), \
             patch('modules.orchestrator.SpeechRecorder'), \
             patch('modules.orchestrator.HailoSTT'):
            self.orchestrator = Orchestrator(
                verbose=False,
                debug=True,
                mpd_controller=self.mock_mpd
            )
            # Inject mocks
            self.orchestrator.mpd_controller = self.mock_mpd
            self.orchestrator.intent_engine = IntentEngine(fuzzy_threshold=50, debug=False)

    def tearDown(self):
        """Clean up after tests"""
        if hasattr(self, 'orchestrator'):
            self.orchestrator.stop()

    def test_tts_initialized_in_orchestrator(self):
        """Test: TTS is initialized in orchestrator
        
        Given: Orchestrator created
        When: Check for TTS instance
        Then: TTS is initialized with volume_manager
        """
        self.assertIsNotNone(self.orchestrator.tts)
        self.assertIsInstance(self.orchestrator.tts, PiperTTS)

    def test_tts_uses_correct_output_device(self):
        """Test: TTS uses correct audio output device from config
        
        Given: Orchestrator with TTS initialized
        When: Check TTS output_device
        Then: Uses config.PIPER_OUTPUT_DEVICE
        """
        expected_device = config.PIPER_OUTPUT_DEVICE
        self.assertEqual(self.orchestrator.tts.output_device, expected_device)

    def test_tts_called_after_intent_execution(self):
        """Test: TTS speak() called after successful intent execution
        
        Given: Transcribed text "play maman"
        When: _process_command() called
        Then: TTS.speak() called with response message
        """
        # Mock speech recorder and STT
        self.orchestrator.speech_recorder.record_command = Mock(return_value=b'fake_audio')
        self.orchestrator.stt.transcribe = Mock(return_value="play maman")
        
        # Mock TTS to track calls
        mock_tts = Mock(spec=PiperTTS)
        mock_tts.speak.return_value = True
        mock_tts.get_response_template.return_value = "Playing maman"
        self.orchestrator.tts = mock_tts
        
        # Execute pipeline
        self.orchestrator._process_command()
        
        # Verify TTS was called
        self.assertTrue(mock_tts.speak.called)
        call_args = mock_tts.speak.call_args[0][0]
        self.assertIn("Playing", call_args)

    def test_tts_called_on_no_intent_match(self):
        """Test: TTS called with error message when no intent matches
        
        Given: Transcribed text "random gibberish"
        When: _process_command() called
        Then: TTS.speak() called with unknown intent message
        """
        # Mock speech recorder and STT
        self.orchestrator.speech_recorder.record_command = Mock(return_value=b'fake_audio')
        self.orchestrator.stt.transcribe = Mock(return_value="random gibberish")
        
        # Mock TTS
        mock_tts = Mock(spec=PiperTTS)
        mock_tts.speak.return_value = True
        mock_tts.get_response_template.return_value = "I didn't understand that"
        self.orchestrator.tts = mock_tts
        
        # Execute pipeline
        self.orchestrator._process_command()
        
        # Verify TTS was called with error message
        self.assertTrue(mock_tts.speak.called)
        mock_tts.get_response_template.assert_called_with('unknown')

    def test_tts_called_on_empty_transcription(self):
        """Test: TTS called with error message when transcription is empty
        
        Given: Empty transcription
        When: _process_command() called
        Then: TTS.speak() called with error message
        """
        # Mock speech recorder and STT
        self.orchestrator.speech_recorder.record_command = Mock(return_value=b'fake_audio')
        self.orchestrator.stt.transcribe = Mock(return_value="")
        
        # Mock TTS
        mock_tts = Mock(spec=PiperTTS)
        mock_tts.speak.return_value = True
        mock_tts.get_response_template.return_value = "Sorry, something went wrong"
        self.orchestrator.tts = mock_tts
        
        # Execute pipeline
        self.orchestrator._process_command()
        
        # Verify TTS was called with error message
        self.assertTrue(mock_tts.speak.called)
        mock_tts.get_response_template.assert_called_with('error')
    
    def test_tts_called_on_empty_audio_data(self):
        """Test: TTS called when audio data is empty
        
        Given: Empty audio data from recording
        When: _process_command() called
        Then: TTS.speak() called with error message
        """
        # Mock speech recorder to return empty audio
        self.orchestrator.speech_recorder.record_command = Mock(return_value=b'')
        self.orchestrator.stt.transcribe = Mock(return_value="")
        
        # Mock TTS
        mock_tts = Mock(spec=PiperTTS)
        mock_tts.speak.return_value = True
        mock_tts.get_response_template.return_value = "Sorry, something went wrong"
        self.orchestrator.tts = mock_tts
        
        # Execute pipeline
        self.orchestrator._process_command()
        
        # Verify TTS was called with error message
        self.assertTrue(mock_tts.speak.called)
        mock_tts.get_response_template.assert_called_with('error')
    
    def test_tts_handles_stt_unavailable(self):
        """Test: TTS called when STT is unavailable
        
        Given: STT not available
        When: _process_command() called
        Then: TTS.speak() called with error message
        """
        # Mock speech recorder
        self.orchestrator.speech_recorder.record_command = Mock(return_value=b'fake_audio')
        
        # Mock STT to be unavailable
        self.orchestrator.stt.is_available = Mock(return_value=False)
        self.orchestrator.stt.reload = Mock()
        self.orchestrator.stt.transcribe = Mock(return_value="")
        
        # Mock TTS
        mock_tts = Mock(spec=PiperTTS)
        mock_tts.speak.return_value = True
        mock_tts.get_response_template.return_value = "Sorry, something went wrong"
        self.orchestrator.tts = mock_tts
        
        # Execute pipeline
        self.orchestrator._process_command()
        
        # Verify TTS was called with error message
        self.assertTrue(mock_tts.speak.called)
        mock_tts.get_response_template.assert_called_with('error')
    
    def test_tts_not_called_when_response_is_none(self):
        """Test: TTS not called when intent execution returns None
        
        Given: Intent execution returns None
        When: _process_command() called
        Then: TTS.speak() not called (response check prevents it)
        """
        # Mock speech recorder and STT
        self.orchestrator.speech_recorder.record_command = Mock(return_value=b'fake_audio')
        self.orchestrator.stt.transcribe = Mock(return_value="play maman")
        
        # Create a real intent
        intent = Intent(
            intent_type='play_music',
            confidence=0.9,
            parameters={'query': 'maman'},
            raw_text='play maman'
        )
        self.orchestrator._classify_intent = Mock(return_value=intent)
        
        # Mock intent execution to return None
        self.orchestrator._execute_intent = Mock(return_value=None)
        
        # Mock TTS
        mock_tts = Mock(spec=PiperTTS)
        mock_tts.speak.return_value = True
        mock_tts.get_response_template.return_value = "Playing maman"
        self.orchestrator.tts = mock_tts
        
        # Execute pipeline
        self.orchestrator._process_command()
        
        # Verify TTS was not called when response is None
        # (The code checks `if response:` before calling speak)
        self.assertFalse(mock_tts.speak.called)

    def test_tts_response_for_each_intent_type(self):
        """Test: TTS provides appropriate response for each intent type
        
        Given: Different intent types
        When: _execute_intent() called
        Then: Returns appropriate response message for TTS
        """
        test_cases = [
            ('play_music', {'query': 'maman'}, "Playing maman"),
            ('pause', {}, "Paused"),
            ('next', {}, "Skipping"),
            ('volume_up', {}, "Volume up"),
            ('add_favorite', {}, "Added to favorites"),
        ]
        
        for intent_type, params, expected_keyword in test_cases:
            intent = Intent(
                intent_type=intent_type,
                confidence=0.9,
                parameters=params,
                raw_text='test'
            )
            
            response = self.orchestrator._execute_intent(intent)
            self.assertIsNotNone(response)
            self.assertIn(expected_keyword, response.lower())

    def test_tts_volume_management(self):
        """Test: TTS uses volume_manager for volume control
        
        Given: Orchestrator with volume_manager
        When: TTS initialized
        Then: TTS has volume_manager reference
        """
        # Create real volume manager
        from modules.volume_manager import VolumeManager
        volume_manager = VolumeManager(mpd_controller=self.mock_mpd)
        
        # Create orchestrator with volume manager
        with patch('modules.orchestrator.WakeWordListener'), \
             patch('modules.orchestrator.SpeechRecorder'), \
             patch('modules.orchestrator.HailoSTT'):
            orchestrator = Orchestrator(
                verbose=False,
                debug=True,
                mpd_controller=self.mock_mpd
            )
            
            # Verify TTS has volume_manager
            self.assertIsNotNone(orchestrator.tts.volume_manager)
            orchestrator.stop()

    def test_tts_error_handling(self):
        """Test: TTS errors are handled gracefully
        
        Given: TTS.speak() raises exception
        When: _process_command() called
        Then: Pipeline continues without crashing
        """
        # Mock speech recorder and STT
        self.orchestrator.speech_recorder.record_command = Mock(return_value=b'fake_audio')
        self.orchestrator.stt.transcribe = Mock(return_value="play maman")
        
        # Mock TTS to raise exception
        mock_tts = Mock(spec=PiperTTS)
        mock_tts.speak.side_effect = Exception("TTS error")
        mock_tts.get_response_template.return_value = "Playing maman"
        self.orchestrator.tts = mock_tts
        
        # Execute pipeline - should not crash
        try:
            self.orchestrator._process_command()
        except Exception as e:
            self.fail(f"Pipeline should handle TTS errors gracefully: {e}")


class TestTTSAudioDevice(unittest.TestCase):
    """Test TTS audio device configuration"""

    def setUp(self):
        """Set up test fixtures"""
        self.project_root = Path(__file__).parent.parent
        self.voice_model = self.project_root / 'resources' / 'voices' / 'en_US-lessac-medium.onnx'

    def test_tts_default_output_device(self):
        """Test: TTS uses default output device when not specified"""
        if not self.voice_model.exists():
            self.skipTest("Voice model not available")
        
        tts = PiperTTS()
        # Should use 'default' from function signature
        self.assertEqual(tts.output_device, 'default')

    def test_tts_custom_output_device(self):
        """Test: TTS accepts custom output device"""
        if not self.voice_model.exists():
            self.skipTest("Voice model not available")
        
        custom_device = 'plughw:0,0'
        tts = PiperTTS(output_device=custom_device)
        self.assertEqual(tts.output_device, custom_device)

    def test_orchestrator_tts_uses_config_device(self):
        """Test: Factory TTS uses config.PIPER_OUTPUT_DEVICE"""
        from modules.factory import create_tts_engine

        with patch('modules.factory.PiperTTS') as mock_tts_class:
            _ = create_tts_engine()

            mock_tts_class.assert_called_once()
            call_kwargs = mock_tts_class.call_args[1]
            self.assertEqual(call_kwargs.get('output_device'), config.PIPER_OUTPUT_DEVICE)


if __name__ == '__main__':
    unittest.main(verbosity=2)
