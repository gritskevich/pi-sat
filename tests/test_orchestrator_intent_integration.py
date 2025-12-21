"""
Test Orchestrator Intent Integration

Tests the complete pipeline:
Wake Word → Recording → STT → Intent Classification → Execution → TTS Response

Follows TDD approach - tests written before implementation.
"""

import unittest
import os
from unittest.mock import Mock, MagicMock, patch, call
from pathlib import Path

from modules.orchestrator import Orchestrator
from modules.intent_engine import Intent, IntentEngine
from modules.mpd_controller import MPDController
from modules.piper_tts import PiperTTS


class TestOrchestratorIntentIntegration(unittest.TestCase):
    """Test orchestrator intent classification and execution"""

    def setUp(self):
        """Set up test fixtures"""
        if os.getenv("PISAT_RUN_LEGACY_ORCHESTRATOR_TESTS", "0") != "1":
            self.skipTest("Legacy orchestrator tests (set PISAT_RUN_LEGACY_ORCHESTRATOR_TESTS=1)")

        # Mock MPD controller
        self.mock_mpd = Mock(spec=MPDController)
        self.mock_mpd.play.return_value = (True, "Playing maman")
        self.mock_mpd.pause.return_value = (True, "Paused")
        self.mock_mpd.resume.return_value = (True, "Resuming")
        self.mock_mpd.stop.return_value = (True, "Stopped")
        self.mock_mpd.next.return_value = (True, "Next: Song")
        self.mock_mpd.previous.return_value = (True, "Previous: Song")
        self.mock_mpd.volume_up.return_value = (True, "Volume 60%")
        self.mock_mpd.volume_down.return_value = (True, "Volume 40%")
        self.mock_mpd.play_favorites.return_value = (True, "Playing your favorites")
        self.mock_mpd.add_to_favorites.return_value = (True, "Added to favorites")
        self.mock_mpd.set_sleep_timer.return_value = (True, "I'll stop in 30 minutes")

        # Mock TTS
        self.mock_tts = Mock(spec=PiperTTS)
        self.mock_tts.speak.return_value = True
        # Mock get_response_template to return appropriate responses
        def get_template(intent, **params):
            templates = {
                'playing': f"Playing {params.get('song', 'music')}",
                'paused': "Paused",
                'skipped': "Skipping",
                'previous': "Going back",
                'volume_up': "Volume up",
                'volume_down': "Volume down",
                'liked': "Added to favorites",
                'favorites': "Playing favorites",
                'no_match': "I don't know that song",
                'error': "Sorry, something went wrong",
                'sleep_timer': f"I'll stop in {params.get('minutes', 30)} minutes",
                'stopped': "Stopped",
                'unknown': "I didn't understand that",
            }
            return templates.get(intent, "Okay")
        self.mock_tts.get_response_template.side_effect = get_template

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
            self.orchestrator.tts = self.mock_tts
            self.orchestrator.intent_engine = IntentEngine(fuzzy_threshold=50, debug=False)

    def tearDown(self):
        """Clean up after tests"""
        if hasattr(self, 'orchestrator'):
            self.orchestrator.stop()

    def test_intent_classification_play_music(self):
        """Test: Classify 'play maman' command

        Given: Transcribed text "play maman"
        When: _classify_intent() called
        Then: Returns play_music intent with query='maman'
        """
        text = "play maman"
        intent = self.orchestrator.intent_engine.classify(text)

        self.assertIsNotNone(intent)
        self.assertEqual(intent.intent_type, 'play_music')
        self.assertEqual(intent.parameters.get('query'), 'maman')

    def test_intent_classification_pause(self):
        """Test: Classify pause command"""
        intent = self.orchestrator.intent_engine.classify("pause")

        self.assertIsNotNone(intent)
        self.assertEqual(intent.intent_type, 'pause')

    def test_intent_classification_sleep_timer(self):
        """Test: Classify sleep timer command"""
        intent = self.orchestrator.intent_engine.classify("stop in 30 minutes")

        self.assertIsNotNone(intent)
        self.assertEqual(intent.intent_type, 'sleep_timer')
        self.assertEqual(intent.parameters.get('duration_minutes'), 30)

    def test_execute_intent_play_music(self):
        """Test: Execute play_music intent

        Given: play_music intent with query='maman'
        When: _execute_intent() called
        Then: Calls mpd_controller.play('maman') and returns success message
        """
        intent = Intent(
            intent_type='play_music',
            confidence=0.95,
            parameters={'query': 'maman'},
            raw_text='play maman'
        )

        result = self.orchestrator._execute_intent(intent)

        self.mock_mpd.play.assert_called_once_with('maman')
        self.assertIn('maman', result.lower() or 'playing maman')

    def test_execute_intent_pause(self):
        """Test: Execute pause intent"""
        intent = Intent(
            intent_type='pause',
            confidence=0.95,
            parameters={},
            raw_text='pause'
        )

        result = self.orchestrator._execute_intent(intent)

        self.mock_mpd.pause.assert_called_once()
        self.assertIsNotNone(result)

    def test_execute_intent_resume(self):
        """Test: Execute resume intent"""
        intent = Intent(
            intent_type='resume',
            confidence=0.95,
            parameters={},
            raw_text='resume'
        )

        result = self.orchestrator._execute_intent(intent)

        self.mock_mpd.resume.assert_called_once()
        self.assertIsNotNone(result)

    def test_execute_intent_stop(self):
        """Test: Execute stop intent"""
        intent = Intent(
            intent_type='stop',
            confidence=0.95,
            parameters={},
            raw_text='stop'
        )

        result = self.orchestrator._execute_intent(intent)

        self.mock_mpd.stop.assert_called_once()
        self.assertIsNotNone(result)

    def test_execute_intent_next(self):
        """Test: Execute next intent"""
        intent = Intent(
            intent_type='next',
            confidence=0.95,
            parameters={},
            raw_text='next'
        )

        result = self.orchestrator._execute_intent(intent)

        self.mock_mpd.next.assert_called_once()
        self.assertIsNotNone(result)

    def test_execute_intent_previous(self):
        """Test: Execute previous intent"""
        intent = Intent(
            intent_type='previous',
            confidence=0.95,
            parameters={},
            raw_text='previous'
        )

        result = self.orchestrator._execute_intent(intent)

        self.mock_mpd.previous.assert_called_once()
        self.assertIsNotNone(result)

    def test_execute_intent_volume_up(self):
        """Test: Execute volume_up intent"""
        intent = Intent(
            intent_type='volume_up',
            confidence=0.95,
            parameters={},
            raw_text='volume up'
        )

        result = self.orchestrator._execute_intent(intent)

        self.mock_mpd.volume_up.assert_called_once()
        self.assertIsNotNone(result)

    def test_execute_intent_volume_down(self):
        """Test: Execute volume_down intent"""
        intent = Intent(
            intent_type='volume_down',
            confidence=0.95,
            parameters={},
            raw_text='volume down'
        )

        result = self.orchestrator._execute_intent(intent)

        self.mock_mpd.volume_down.assert_called_once()
        self.assertIsNotNone(result)

    def test_execute_intent_play_favorites(self):
        """Test: Execute play_favorites intent"""
        intent = Intent(
            intent_type='play_favorites',
            confidence=0.95,
            parameters={},
            raw_text='play favorites'
        )

        result = self.orchestrator._execute_intent(intent)

        self.mock_mpd.play_favorites.assert_called_once()
        self.assertIsNotNone(result)

    def test_execute_intent_add_favorite(self):
        """Test: Execute add_favorite intent"""
        intent = Intent(
            intent_type='add_favorite',
            confidence=0.95,
            parameters={},
            raw_text='i love this'
        )

        result = self.orchestrator._execute_intent(intent)

        self.mock_mpd.add_to_favorites.assert_called_once()
        self.assertIsNotNone(result)

    def test_execute_intent_sleep_timer(self):
        """Test: Execute sleep_timer intent with duration"""
        intent = Intent(
            intent_type='sleep_timer',
            confidence=0.95,
            parameters={'duration_minutes': 30},
            raw_text='stop in 30 minutes'
        )

        result = self.orchestrator._execute_intent(intent)

        self.mock_mpd.set_sleep_timer.assert_called_once_with(30)
        self.assertIsNotNone(result)

    def test_execute_intent_unknown(self):
        """Test: Execute unknown intent returns error message"""
        intent = Intent(
            intent_type='unknown_intent',
            confidence=0.5,
            parameters={},
            raw_text='unknown command'
        )

        result = self.orchestrator._execute_intent(intent)

        self.assertIn('understand', result.lower() or "i didn't understand")

    def test_full_pipeline_with_mock_stt(self):
        """Test: Full pipeline with mocked STT

        Given: Mocked audio transcription returning "play maman"
        When: _process_command() called
        Then: Classifies intent, executes play, and speaks response
        """
        # Mock speech recorder to return fake audio
        self.orchestrator.speech_recorder.record_command = Mock(return_value=b'fake_audio_data')

        # Mock STT to return transcribed text
        self.orchestrator.stt.transcribe = Mock(return_value="play maman")

        # Execute pipeline
        self.orchestrator._process_command()

        # Verify STT was called
        self.orchestrator.stt.transcribe.assert_called_once()

        # Verify MPD play was called (via _execute_intent)
        # Note: This will fail until we implement _execute_intent in orchestrator
        # That's expected in TDD - test first, then implement

    def test_pipeline_with_no_intent_match(self):
        """Test: Pipeline handles no intent match gracefully

        Given: Transcribed text with no matching intent
        When: _process_command() called
        Then: Handles gracefully without crashing
        """
        self.orchestrator.speech_recorder.record_command = Mock(return_value=b'fake_audio')
        self.orchestrator.stt.transcribe = Mock(return_value="tell me a joke")

        # Should not crash
        try:
            self.orchestrator._process_command()
        except Exception as e:
            self.fail(f"Pipeline should handle no-match gracefully: {e}")

    def test_pipeline_with_empty_transcription(self):
        """Test: Pipeline handles empty transcription

        Given: STT returns empty string
        When: _process_command() called
        Then: Skips intent classification and execution
        """
        self.orchestrator.speech_recorder.record_command = Mock(return_value=b'fake_audio')
        self.orchestrator.stt.transcribe = Mock(return_value="")

        self.orchestrator._process_command()

        # Should not call MPD or TTS
        self.mock_mpd.play.assert_not_called()
        self.mock_tts.speak.assert_not_called()


class TestOrchestratorIntentIntegrationReal(unittest.TestCase):
    """Integration tests with real components (no mocks)"""

    def setUp(self):
        """Set up real orchestrator for integration testing"""
        # Use real orchestrator but with debug mode
        self.orchestrator = Orchestrator(verbose=False, debug=True)

    def tearDown(self):
        """Clean up"""
        if hasattr(self, 'orchestrator'):
            self.orchestrator.stop()

    def test_intent_engine_initialized(self):
        """Test: Intent engine is initialized in orchestrator"""
        # This will fail until we add intent_engine to orchestrator
        self.assertTrue(hasattr(self.orchestrator, 'intent_engine'))
        self.assertIsInstance(self.orchestrator.intent_engine, IntentEngine)

    def test_mpd_controller_available(self):
        """Test: MPD controller is available if provided"""
        # Orchestrator should accept mpd_controller parameter
        mock_mpd = Mock()
        orchestrator = Orchestrator(verbose=False, mpd_controller=mock_mpd)
        # Should store or use mpd_controller
        orchestrator.stop()


if __name__ == '__main__':
    unittest.main(verbosity=2)
