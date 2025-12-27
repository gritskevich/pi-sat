"""
Tests for CommandProcessor Module

Demonstrates improved testability with dependency injection.
All dependencies are mocked - no real audio hardware required.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from modules.command_processor import CommandProcessor
from modules.interfaces import Intent
from modules.command_validator import ValidationResult
from modules.music_resolver import MusicResolution


class TestCommandProcessor(unittest.TestCase):
    """Test CommandProcessor with mocked dependencies"""

    def setUp(self):
        """Set up test fixtures with mocked dependencies"""
        # Create mocks for all dependencies
        self.mock_speech_recorder = Mock()
        self.mock_stt = Mock()
        self.mock_intent_engine = Mock()
        self.mock_mpd = Mock()
        self.mock_tts = Mock()
        self.mock_volume_manager = Mock()

        # Configure mocks with default behavior
        self.mock_speech_recorder.record_command.return_value = b"fake audio data"
        self.mock_stt.transcribe.return_value = "play maman"
        self.mock_stt.is_available.return_value = True

        # Configure default intent
        self.default_intent = Intent(
            intent_type='play_music',
            confidence=0.95,
            parameters={'query': 'maman'},
            raw_text='play maman',
            language='fr'
        )
        self.mock_intent_engine.classify.return_value = self.default_intent

        # Configure MPD default response (success, message, confidence)
        self.mock_mpd.play.return_value = (True, "Playing maman", 0.9)

        # Configure MPD music library (needed for MusicResolver)
        mock_music_library = Mock()
        mock_music_library.search.return_value = [("maman.mp3", 0.9)]
        self.mock_mpd.get_music_library.return_value = mock_music_library

        # Configure TTS default response template
        self.mock_tts.get_response_template.return_value = "Playing maman"
        self.mock_tts.speak.return_value = True

        # Configure command validator to always validate successfully
        self.mock_validator = Mock()
        self.mock_validator.validate.return_value = ValidationResult.valid(
            message="D'accord, je joue maman",
            params={'query': 'maman'},
            confidence=0.9
        )

        # Create CommandProcessor with mocked dependencies
        with patch('modules.command_processor.MusicResolver') as MockMusicResolver:
            # Mock MusicResolver.resolve() to return a MusicResolution
            mock_resolver = Mock()
            mock_resolver.resolve.return_value = MusicResolution(
                query="maman",
                confidence=0.9,
                matched_file="maman.mp3"
            )
            MockMusicResolver.return_value = mock_resolver

            self.processor = CommandProcessor(
                speech_recorder=self.mock_speech_recorder,
                stt_engine=self.mock_stt,
                intent_engine=self.mock_intent_engine,
                mpd_controller=self.mock_mpd,
                tts_engine=self.mock_tts,
                volume_manager=self.mock_volume_manager,
                command_validator=self.mock_validator,
                debug=True,
                verbose=False
            )

    def test_initialization(self):
        """Test: CommandProcessor initializes with dependencies"""
        self.assertIsNotNone(self.processor)
        self.assertEqual(self.processor.speech_recorder, self.mock_speech_recorder)
        self.assertEqual(self.processor.stt, self.mock_stt)
        self.assertEqual(self.processor.intent_engine, self.mock_intent_engine)

    @unittest.skip("Volume ducking removed from command processor")
    def test_process_command_success(self):
        """Test: Successful command processing"""
        success = self.processor.process_command()

        self.assertTrue(success)

        # Verify pipeline steps
        self.mock_volume_manager.duck_music_volume.assert_called_once()
        self.mock_speech_recorder.record_command.assert_called_once()
        self.mock_stt.transcribe.assert_called_once()
        self.mock_intent_engine.classify.assert_called_once_with("play maman")
        self.mock_validator.validate.assert_called_once()
        self.mock_mpd.play.assert_called_once()
        # TTS speaks validation feedback (execution response is empty)
        self.assertEqual(self.mock_tts.speak.call_count, 1)
        self.mock_volume_manager.restore_music_volume.assert_called_once()

    @unittest.skip("Volume ducking removed from command processor")
    def test_process_command_empty_audio(self):
        """Test: Handle empty audio recording"""
        self.mock_speech_recorder.record_command.return_value = b""

        success = self.processor.process_command()

        self.assertFalse(success)
        self.mock_tts.speak.assert_called_once()  # Error message
        self.mock_volume_manager.restore_music_volume.assert_called_once()

    @unittest.skip("Volume ducking removed from command processor")
    def test_process_command_empty_transcription(self):
        """Test: Handle empty transcription"""
        self.mock_stt.transcribe.return_value = ""

        success = self.processor.process_command()

        self.assertFalse(success)
        self.mock_tts.get_response_template.assert_called_with('error')
        self.mock_volume_manager.restore_music_volume.assert_called_once()

    @unittest.skip("Volume ducking removed from command processor")
    def test_process_command_no_intent_match(self):
        """Test: Handle no intent match"""
        self.mock_intent_engine.classify.return_value = None

        success = self.processor.process_command()

        self.assertFalse(success)
        self.mock_tts.get_response_template.assert_called_with('unknown')
        self.mock_volume_manager.restore_music_volume.assert_called_once()

    @unittest.skip("Volume ducking removed from command processor")
    def test_process_command_stt_unavailable(self):
        """Test: Handle STT unavailable"""
        self.mock_stt.is_available.return_value = False
        self.mock_stt.reload.return_value = None

        success = self.processor.process_command()

        self.assertFalse(success)
        self.mock_stt.reload.assert_called_once()
        self.mock_volume_manager.restore_music_volume.assert_called_once()

    def test_execute_intent_play_music(self):
        """Test: Execute play_music intent"""
        intent = Intent(
            intent_type='play_music',
            confidence=0.95,
            parameters={'query': 'maman'},
            raw_text='play maman'
        )

        self.mock_mpd.play.return_value = (True, "Playing")
        response = self.processor._execute_intent(intent)

        self.mock_mpd.play.assert_called_once_with('maman')
        self.assertIsNotNone(response)

    def test_execute_intent_pause(self):
        """Test: Execute pause intent"""
        intent = Intent(
            intent_type='pause',
            confidence=0.98,
            parameters={},
            raw_text='pause'
        )

        self.mock_mpd.pause.return_value = (True, "Paused")
        response = self.processor._execute_intent(intent)

        self.mock_mpd.pause.assert_called_once()
        self.assertIsNotNone(response)

    def test_execute_intent_next(self):
        """Test: Execute next intent"""
        intent = Intent(
            intent_type='next',
            confidence=0.97,
            parameters={},
            raw_text='skip'
        )

        self.mock_mpd.next.return_value = (True, "Next track")
        response = self.processor._execute_intent(intent)

        self.mock_mpd.next.assert_called_once()
        self.assertIsNotNone(response)

    def test_execute_intent_volume_up(self):
        """Test: Execute volume_up intent"""
        intent = Intent(
            intent_type='volume_up',
            confidence=0.92,
            parameters={},
            raw_text='louder'
        )

        self.mock_volume_manager.music_volume_up.return_value = (True, "Music volume 70%")
        response = self.processor._execute_intent(intent)

        self.mock_volume_manager.music_volume_up.assert_called_once()
        self.assertIsNotNone(response)

    def test_execute_intent_add_favorite(self):
        """Test: Execute add_favorite intent"""
        intent = Intent(
            intent_type='add_favorite',
            confidence=0.94,
            parameters={},
            raw_text='i love this song'
        )

        self.mock_mpd.add_to_favorites.return_value = (True, "Added to favorites")
        response = self.processor._execute_intent(intent)

        self.mock_mpd.add_to_favorites.assert_called_once()
        self.assertIsNotNone(response)

    def test_execute_intent_sleep_timer(self):
        """Test: Execute sleep_timer intent"""
        intent = Intent(
            intent_type='sleep_timer',
            confidence=0.90,
            parameters={'duration_minutes': 30},
            raw_text='stop in 30 minutes'
        )

        self.mock_mpd.set_sleep_timer.return_value = (True, "Timer set")
        response = self.processor._execute_intent(intent)

        self.mock_mpd.set_sleep_timer.assert_called_once_with(30)
        self.assertIsNotNone(response)

    def test_execute_intent_play_favorites(self):
        """Test: Execute play_favorites intent"""
        intent = Intent(
            intent_type='play_favorites',
            confidence=0.93,
            parameters={},
            raw_text='play my favorites'
        )

        self.mock_mpd.play_favorites.return_value = (True, "Playing favorites")
        response = self.processor._execute_intent(intent)

        self.mock_mpd.play_favorites.assert_called_once()
        self.assertIsNotNone(response)

    def test_execute_intent_unknown(self):
        """Test: Execute unknown intent"""
        intent = Intent(
            intent_type='unknown_intent',
            confidence=0.85,
            parameters={},
            raw_text='do something weird'
        )

        response = self.processor._execute_intent(intent)

        self.assertIsNotNone(response)

    @unittest.skip("Volume ducking removed from command processor")
    def test_volume_ducking_always_restored(self):
        """Test: Volume is always restored, even on errors"""
        # Simulate error during processing
        self.mock_speech_recorder.record_command.side_effect = Exception("Recording error")

        try:
            self.processor.process_command()
        except:
            pass

        # Volume should still be restored
        self.mock_volume_manager.restore_music_volume.assert_called_once()

    def test_classify_intent_empty_text(self):
        """Test: Classify intent with empty text"""
        result = self.processor._classify_intent("")
        self.assertIsNone(result)

        result = self.processor._classify_intent("   ")
        self.assertIsNone(result)

    def test_classify_intent_exception(self):
        """Test: Handle exception during classification"""
        self.mock_intent_engine.classify.side_effect = Exception("Classification error")

        result = self.processor._classify_intent("test")
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
