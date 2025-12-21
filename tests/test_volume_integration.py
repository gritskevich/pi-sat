"""
Test Volume Manager Integration - Orchestrator and PiperTTS

Tests volume management integration with orchestrator and TTS.
Useful integration tests, not fake ones.
"""

import unittest
import os
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import config

from modules.volume_manager import VolumeManager
from modules.piper_tts import PiperTTS
from modules.orchestrator import Orchestrator


class TestVolumeIntegration(unittest.TestCase):
    """Test volume manager integration with other modules"""

    def setUp(self):
        """Set up test fixtures"""
        if os.getenv("PISAT_RUN_LEGACY_ORCHESTRATOR_TESTS", "0") != "1":
            self.skipTest("Legacy orchestrator tests (set PISAT_RUN_LEGACY_ORCHESTRATOR_TESTS=1)")

        self.mock_mpd = Mock()
        self.mock_mpd.client = Mock()
        self.mock_mpd._ensure_connection = MagicMock()
        self.mock_mpd._ensure_connection.return_value.__enter__ = Mock(return_value=None)
        self.mock_mpd._ensure_connection.return_value.__exit__ = Mock(return_value=None)
        self.mock_mpd.client.status.return_value = {'volume': '50'}

    def test_orchestrator_volume_manager_initialization(self):
        """Test: Orchestrator initializes VolumeManager correctly"""
        orchestrator = Orchestrator(verbose=False, debug=True, mpd_controller=self.mock_mpd)
        
        self.assertIsNotNone(orchestrator.volume_manager)
        self.assertEqual(orchestrator.volume_manager.mpd_controller, self.mock_mpd)

    def test_orchestrator_duck_volume_on_wake_word(self):
        """Test: Orchestrator ducks volume when processing command"""
        orchestrator = Orchestrator(verbose=False, debug=True, mpd_controller=self.mock_mpd)
        orchestrator.volume_manager._mpd_volume_available = True
        orchestrator.volume_manager.duck_music_volume = Mock(return_value=True)
        orchestrator.volume_manager.restore_music_volume = Mock(return_value=True)
        
        # Mock recording to avoid actual mic access
        orchestrator._record_command = Mock(return_value=b'fake_audio')
        orchestrator._transcribe_audio = Mock(return_value="")
        
        # Process command (simulates wake word detection)
        orchestrator._process_command()
        
        # Verify ducking was called
        orchestrator.volume_manager.duck_music_volume.assert_called_once()
        duck_call = orchestrator.volume_manager.duck_music_volume.call_args
        self.assertEqual(duck_call.kwargs['duck_to'], config.VOLUME_DUCK_LEVEL)
        
        # Verify restore was called
        orchestrator.volume_manager.restore_music_volume.assert_called_once()

    def test_orchestrator_restores_volume_on_error(self):
        """Test: Orchestrator restores volume even if processing fails"""
        orchestrator = Orchestrator(verbose=False, debug=True, mpd_controller=self.mock_mpd)
        orchestrator.volume_manager._mpd_volume_available = True
        orchestrator.volume_manager.duck_music_volume = Mock(return_value=True)
        orchestrator.volume_manager.restore_music_volume = Mock(return_value=True)
        
        # Make recording raise an exception
        orchestrator._record_command = Mock(side_effect=Exception("Test error"))
        
        # Process should still restore volume
        try:
            orchestrator._process_command()
        except Exception:
            pass
        
        # Verify restore was called despite error
        orchestrator.volume_manager.restore_music_volume.assert_called_once()

    def test_piper_tts_with_volume_manager(self):
        """Test: PiperTTS uses volume_manager for volume control"""
        volume_manager = VolumeManager(mpd_controller=None)
        volume_manager._alsa_available = True
        volume_manager.get_tts_volume = Mock(return_value=70)
        volume_manager.set_tts_volume = Mock(return_value=True)
        
        tts = PiperTTS(volume_manager=volume_manager)
        
        # Mock the actual speak command to avoid running piper
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            tts.speak("Test")
        
        # Verify volume was set (to config.TTS_VOLUME)
        volume_manager.set_tts_volume.assert_called()
        # Should be called twice: once to set, once to restore
        self.assertEqual(volume_manager.set_tts_volume.call_count, 2)
        
        # First call should set to config.TTS_VOLUME
        first_call = volume_manager.set_tts_volume.call_args_list[0]
        self.assertEqual(first_call[0][0], config.TTS_VOLUME)
        
        # Second call should restore original
        second_call = volume_manager.set_tts_volume.call_args_list[1]
        self.assertEqual(second_call[0][0], 70)

    def test_piper_tts_custom_volume(self):
        """Test: PiperTTS accepts custom volume parameter"""
        volume_manager = VolumeManager(mpd_controller=None)
        volume_manager._alsa_available = True
        volume_manager.get_tts_volume = Mock(return_value=70)
        volume_manager.set_tts_volume = Mock(return_value=True)
        
        tts = PiperTTS(volume_manager=volume_manager)
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            tts.speak("Test", volume=90)
        
        # Verify custom volume was used
        first_call = volume_manager.set_tts_volume.call_args_list[0]
        self.assertEqual(first_call[0][0], 90)

    def test_piper_tts_without_volume_manager(self):
        """Test: PiperTTS works without volume_manager (backward compatible)"""
        tts = PiperTTS(volume_manager=None)
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            success = tts.speak("Test")
        
        self.assertTrue(success)

    def test_volume_manager_separate_music_tts(self):
        """Test: Music and TTS volumes are managed independently"""
        volume_manager = VolumeManager(mpd_controller=self.mock_mpd)
        volume_manager._mpd_volume_available = True
        volume_manager._alsa_available = True
        
        # Set music volume
        volume_manager.get_music_volume = Mock(return_value=50)
        volume_manager.set_music_volume = Mock(return_value=True)
        volume_manager.set_music_volume(60)
        
        # Set TTS volume (should be independent)
        volume_manager.get_tts_volume = Mock(return_value=70)
        volume_manager.set_tts_volume = Mock(return_value=True)
        volume_manager.set_tts_volume(80)
        
        # Verify both were set independently
        music_calls = [c[0][0] for c in volume_manager.set_music_volume.call_args_list]
        tts_calls = [c[0][0] for c in volume_manager.set_tts_volume.call_args_list]
        
        self.assertIn(60, music_calls)
        self.assertIn(80, tts_calls)
        self.assertNotEqual(music_calls, tts_calls)

    def test_volume_ducking_preserves_tts_volume(self):
        """Test: Ducking music volume doesn't affect TTS volume"""
        volume_manager = VolumeManager(mpd_controller=self.mock_mpd)
        volume_manager._mpd_volume_available = True
        volume_manager._alsa_available = True
        
        # Set initial volumes
        volume_manager.get_music_volume = Mock(return_value=60)
        volume_manager.get_tts_volume = Mock(return_value=80)
        volume_manager.set_music_volume = Mock(return_value=True)
        volume_manager.set_tts_volume = Mock(return_value=True)
        volume_manager.tts_volume = 80  # Set initial TTS volume
        
        # Duck music volume
        volume_manager.duck_music_volume(duck_to=20)
        
        # Verify only music volume was changed
        volume_manager.set_music_volume.assert_called_with(20)
        volume_manager.set_tts_volume.assert_not_called()
        
        # TTS volume should still be 80 (unchanged)
        self.assertEqual(volume_manager.tts_volume, 80)


if __name__ == '__main__':
    unittest.main()
