"""
Test Volume Manager - Unified volume control

Tests volume management for music and TTS with MPD/ALSA fallback.
Follows patterns from CLAUDE.md - useful tests, not fake ones.
"""

import unittest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, call
import subprocess

from modules.volume_manager import VolumeManager


class TestVolumeManager(unittest.TestCase):
    """Test VolumeManager with mocked MPD and ALSA"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_mpd = Mock()
        self.mock_mpd.client = Mock()
        self.mock_mpd._ensure_connection = MagicMock()
        self.mock_mpd._ensure_connection.return_value.__enter__ = Mock(return_value=None)
        self.mock_mpd._ensure_connection.return_value.__exit__ = Mock(return_value=None)

    def test_initialization_without_mpd(self):
        """Test: VolumeManager initializes without MPD controller"""
        manager = VolumeManager(mpd_controller=None)
        
        self.assertIsNone(manager.mpd_controller)
        self.assertFalse(manager._mpd_volume_available)
        self.assertIsNone(manager.music_volume)
        self.assertIsNone(manager.tts_volume)
        self.assertFalse(manager._ducking_active)

    def test_initialization_with_mpd(self):
        """Test: VolumeManager initializes with MPD controller"""
        self.mock_mpd.client.status.return_value = {'volume': '50'}
        
        manager = VolumeManager(mpd_controller=self.mock_mpd)
        
        self.assertEqual(manager.mpd_controller, self.mock_mpd)
        # MPD volume availability depends on status check

    def test_get_music_volume_mpd_available(self):
        """Test: Get music volume from MPD when available"""
        self.mock_mpd.client.status.return_value = {'volume': '75'}
        manager = VolumeManager(mpd_controller=self.mock_mpd)
        manager._mpd_volume_available = True
        
        volume = manager.get_music_volume()
        
        self.assertEqual(volume, 75)
        self.assertEqual(manager.music_volume, 75)
        self.mock_mpd.client.status.assert_called()

    def test_get_music_volume_mpd_unavailable(self):
        """Test: Get music volume falls back to ALSA when MPD unavailable"""
        manager = VolumeManager(mpd_controller=self.mock_mpd)
        manager._mpd_volume_available = False
        manager._alsa_available = True
        
        with patch.object(manager, '_get_alsa_volume', return_value=60):
            volume = manager.get_music_volume()
        
        self.assertEqual(volume, 60)
        self.assertEqual(manager.music_volume, 60)

    def test_set_music_volume_mpd(self):
        """Test: Set music volume via MPD"""
        self.mock_mpd.client.status.return_value = {'volume': '50'}
        manager = VolumeManager(mpd_controller=self.mock_mpd)
        manager._mpd_volume_available = True
        
        success = manager.set_music_volume(80)
        
        self.assertTrue(success)
        self.mock_mpd.client.setvol.assert_called_once_with(80)
        self.assertEqual(manager.music_volume, 80)

    def test_set_music_volume_alsa_fallback(self):
        """Test: Set music volume via ALSA when MPD unavailable"""
        manager = VolumeManager(mpd_controller=self.mock_mpd)
        manager._mpd_volume_available = False
        manager._alsa_available = True
        
        with patch.object(manager, '_set_alsa_volume', return_value=True):
            success = manager.set_music_volume(70)
        
        self.assertTrue(success)
        self.assertEqual(manager.music_volume, 70)

    def test_volume_clamping(self):
        """Test: Volume values are clamped to 0-100 range"""
        manager = VolumeManager(mpd_controller=None)
        manager._alsa_available = True
        
        with patch.object(manager, '_set_alsa_volume', return_value=True) as mock_set:
            # Test values outside range
            manager.set_music_volume(-10)
            mock_set.assert_called_with(0)
            
            manager.set_music_volume(150)
            mock_set.assert_called_with(100)

    def test_duck_music_volume(self):
        """Test: Duck music volume saves original and lowers volume"""
        self.mock_mpd.client.status.return_value = {'volume': '60'}
        manager = VolumeManager(mpd_controller=self.mock_mpd)
        manager._mpd_volume_available = True
        
        with patch.object(manager, 'get_music_volume', return_value=60):
            with patch.object(manager, 'set_music_volume', return_value=True) as mock_set:
                success = manager.duck_music_volume(duck_to=20)
        
        self.assertTrue(success)
        self.assertEqual(manager._music_original_volume, 60)
        self.assertTrue(manager._ducking_active)
        mock_set.assert_called_once_with(20)

    def test_duck_music_volume_already_ducked(self):
        """Test: Ducking when already ducked returns True without change"""
        manager = VolumeManager(mpd_controller=None)
        manager._ducking_active = True
        
        success = manager.duck_music_volume(duck_to=20)
        
        self.assertTrue(success)

    def test_duck_music_volume_no_control(self):
        """Test: Ducking fails gracefully when no volume control available"""
        manager = VolumeManager(mpd_controller=None)
        manager._mpd_volume_available = False
        manager._alsa_available = False
        
        with patch.object(manager, 'get_music_volume', return_value=None):
            success = manager.duck_music_volume(duck_to=20)
        
        self.assertFalse(success)
        self.assertFalse(manager._ducking_active)

    def test_restore_music_volume(self):
        """Test: Restore music volume after ducking"""
        manager = VolumeManager(mpd_controller=self.mock_mpd)
        manager._ducking_active = True
        manager._music_original_volume = 60
        manager._mpd_volume_available = True
        
        with patch.object(manager, 'set_music_volume', return_value=True) as mock_set:
            success = manager.restore_music_volume()
        
        self.assertTrue(success)
        self.assertFalse(manager._ducking_active)
        self.assertIsNone(manager._music_original_volume)
        mock_set.assert_called_once_with(60)

    def test_restore_music_volume_not_ducked(self):
        """Test: Restore when not ducked returns True"""
        manager = VolumeManager(mpd_controller=None)
        manager._ducking_active = False
        
        success = manager.restore_music_volume()
        
        self.assertTrue(success)

    def test_restore_music_volume_no_original(self):
        """Test: Restore fails gracefully when original volume not saved"""
        manager = VolumeManager(mpd_controller=None)
        manager._ducking_active = True
        manager._music_original_volume = None
        
        success = manager.restore_music_volume()
        
        self.assertFalse(success)
        self.assertFalse(manager._ducking_active)

    def test_tts_volume_control(self):
        """Test: TTS volume control independent of music volume"""
        manager = VolumeManager(mpd_controller=None)
        manager._alsa_available = True
        
        with patch.object(manager, '_get_alsa_volume', return_value=50):
            tts_volume = manager.get_tts_volume()
        
        self.assertEqual(tts_volume, 50)
        self.assertEqual(manager.tts_volume, 50)
        
        with patch.object(manager, '_set_alsa_volume', return_value=True):
            success = manager.set_tts_volume(80)
        
        self.assertTrue(success)
        self.assertEqual(manager.tts_volume, 80)

    def test_music_volume_up(self):
        """Test: Increase music volume"""
        manager = VolumeManager(mpd_controller=None)
        manager.get_music_volume = Mock(return_value=50)
        manager.set_music_volume = Mock(return_value=True)
        
        success, message = manager.music_volume_up(amount=10)
        
        self.assertTrue(success)
        self.assertIn("60", message)
        manager.set_music_volume.assert_called_once_with(60)

    def test_music_volume_up_caps_at_100(self):
        """Test: Volume increase caps at 100%"""
        manager = VolumeManager(mpd_controller=None)
        manager.get_music_volume = Mock(return_value=95)
        manager.set_music_volume = Mock(return_value=True)
        
        success, message = manager.music_volume_up(amount=10)
        
        self.assertTrue(success)
        manager.set_music_volume.assert_called_once_with(100)

    def test_music_volume_down(self):
        """Test: Decrease music volume"""
        manager = VolumeManager(mpd_controller=None)
        manager.get_music_volume = Mock(return_value=50)
        manager.set_music_volume = Mock(return_value=True)
        
        success, message = manager.music_volume_down(amount=10)
        
        self.assertTrue(success)
        self.assertIn("40", message)
        manager.set_music_volume.assert_called_once_with(40)

    def test_music_volume_down_floors_at_0(self):
        """Test: Volume decrease floors at 0%"""
        manager = VolumeManager(mpd_controller=None)
        manager.get_music_volume = Mock(return_value=5)
        manager.set_music_volume = Mock(return_value=True)
        
        success, message = manager.music_volume_down(amount=10)
        
        self.assertTrue(success)
        manager.set_music_volume.assert_called_once_with(0)

    def test_volume_control_unavailable(self):
        """Test: Volume operations return appropriate values when unavailable"""
        manager = VolumeManager(mpd_controller=None)
        manager._mpd_volume_available = False
        manager._alsa_available = False
        
        volume = manager.get_music_volume()
        self.assertIsNone(volume)
        
        success = manager.set_music_volume(50)
        self.assertFalse(success)
        
        success, message = manager.music_volume_up(10)
        self.assertFalse(success)
        self.assertIn("unavailable", message.lower())

    def test_alsa_volume_parsing(self):
        """Test: ALSA volume parsing from amixer output"""
        manager = VolumeManager(mpd_controller=None)
        
        # Test various amixer output formats
        test_cases = [
            ("Front Left: Playback 26304 [40%] [on]", 40),
            ("Mono: Playback 32768 [50%] [off]", 50),
            ("  [75%]  ", 75),
        ]
        
        for output_line, expected_volume in test_cases:
            with patch('subprocess.run') as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = output_line
                
                volume = manager._get_alsa_volume()
                self.assertEqual(volume, expected_volume, f"Failed for: {output_line}")

    def test_alsa_volume_set(self):
        """Test: ALSA volume setting via amixer"""
        manager = VolumeManager(mpd_controller=None)
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            success = manager._set_alsa_volume(75)
        
        self.assertTrue(success)
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertEqual(args[0], 'amixer')
        self.assertEqual(args[1], 'set')
        self.assertEqual(args[2], 'Master')
        self.assertEqual(args[3], '75%')

    def test_duck_restore_cycle(self):
        """Test: Complete duck/restore cycle preserves original volume"""
        self.mock_mpd.client.status.return_value = {'volume': '70'}
        manager = VolumeManager(mpd_controller=self.mock_mpd)
        manager._mpd_volume_available = True
        
        # Initial volume
        with patch.object(manager, 'get_music_volume', return_value=70):
            original = manager.get_music_volume()
        
        # Duck
        with patch.object(manager, 'get_music_volume', return_value=70):
            with patch.object(manager, 'set_music_volume', return_value=True):
                manager.duck_music_volume(duck_to=20)
        
        self.assertEqual(manager._music_original_volume, 70)
        self.assertTrue(manager._ducking_active)
        
        # Restore
        with patch.object(manager, 'set_music_volume', return_value=True) as mock_set:
            manager.restore_music_volume()
        
        mock_set.assert_called_once_with(70)
        self.assertFalse(manager._ducking_active)
        self.assertIsNone(manager._music_original_volume)


if __name__ == '__main__':
    unittest.main()

