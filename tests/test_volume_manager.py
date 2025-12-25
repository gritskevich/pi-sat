"""
Test Volume Manager - PulseAudio/PipeWire volume control

Tests simplified single master volume via pactl.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import subprocess

from modules.volume_manager import VolumeManager
import config


class TestVolumeManager(unittest.TestCase):
    """Test VolumeManager with mocked PulseAudio/PipeWire"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_mpd = Mock()
        self.mock_mpd.client = Mock()
        self.mock_mpd._ensure_connection = MagicMock()
        self.mock_mpd._ensure_connection.return_value.__enter__ = Mock(return_value=None)
        self.mock_mpd._ensure_connection.return_value.__exit__ = Mock(return_value=None)

    @patch('subprocess.run')
    def test_initialization_without_mpd(self, mock_run):
        """Test: VolumeManager initializes without MPD controller"""
        mock_run.return_value.returncode = 0
        manager = VolumeManager(mpd_controller=None)
        
        self.assertIsNone(manager.mpd_controller)
        self.assertIsNone(manager.master_volume)

    @patch('subprocess.run')
    def test_initialization_with_mpd(self, mock_run):
        """Test: VolumeManager initializes with MPD controller"""
        mock_run.return_value.returncode = 0
        manager = VolumeManager(mpd_controller=self.mock_mpd)
        
        self.assertEqual(manager.mpd_controller, self.mock_mpd)

    @patch('subprocess.run')
    def test_pulse_available_detection(self, mock_run):
        """Test: Detects PulseAudio/PipeWire availability"""
        mock_run.return_value.returncode = 0
        manager = VolumeManager(mpd_controller=None)
        
        self.assertTrue(manager._pulse_available)

    @patch('subprocess.run')
    def test_pulse_unavailable_detection(self, mock_run):
        """Test: Detects when PulseAudio/PipeWire is unavailable"""
        mock_run.return_value.returncode = 1
        manager = VolumeManager(mpd_controller=None)
        
        self.assertFalse(manager._pulse_available)

    @patch('subprocess.run')
    def test_get_master_volume(self, mock_run):
        """Test: Get master volume from PulseAudio"""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Volume: front-left: 32768 /  50% / -18.06 dB"
        
        manager = VolumeManager(mpd_controller=None)
        manager.master_volume = None  # Force read from pactl
        
        volume = manager.get_master_volume()
        self.assertEqual(volume, 50)

    @patch('subprocess.run')
    def test_get_master_volume_cached(self, mock_run):
        """Test: Returns cached volume without calling pactl"""
        mock_run.return_value.returncode = 0
        manager = VolumeManager(mpd_controller=None)
        manager.master_volume = 75
        
        volume = manager.get_master_volume()
        self.assertEqual(volume, 75)

    @patch('subprocess.run')
    def test_set_master_volume(self, mock_run):
        """Test: Set master volume via PulseAudio"""
        mock_run.return_value.returncode = 0
        manager = VolumeManager(mpd_controller=None)
        
        success = manager.set_master_volume(80)
        
        self.assertTrue(success)
        self.assertEqual(manager.master_volume, 80)
        # Verify pactl was called with correct args
        calls = [c for c in mock_run.call_args_list if 'set-sink-volume' in str(c)]
        self.assertTrue(len(calls) > 0)

    @patch('subprocess.run')
    def test_volume_clamping(self, mock_run):
        """Test: Volume values are clamped to 0-100 range"""
        mock_run.return_value.returncode = 0
        manager = VolumeManager(mpd_controller=None)
        
        manager.set_master_volume(-10)
        self.assertEqual(manager.master_volume, 0)
        
        manager.set_master_volume(150)
        self.assertEqual(manager.master_volume, 100)

    @patch('subprocess.run')
    def test_music_volume_up(self, mock_run):
        """Test: Increase master volume"""
        mock_run.return_value.returncode = 0
        manager = VolumeManager(mpd_controller=None)
        manager.master_volume = 40
        
        success, message = manager.music_volume_up(amount=10)
        
        self.assertTrue(success)
        self.assertEqual(manager.master_volume, 50)
        self.assertIn("50", message)

    @patch('subprocess.run')
    def test_music_volume_up_caps_at_max_volume(self, mock_run):
        """Test: Volume increase caps at MAX_VOLUME"""
        mock_run.return_value.returncode = 0
        manager = VolumeManager(mpd_controller=None)
        max_vol = min(100, config.MAX_VOLUME)
        manager.master_volume = max_vol - 5
        
        success, message = manager.music_volume_up(amount=10)
        
        self.assertTrue(success)
        self.assertEqual(manager.master_volume, max_vol)

    @patch('subprocess.run')
    def test_music_volume_down(self, mock_run):
        """Test: Decrease master volume"""
        mock_run.return_value.returncode = 0
        manager = VolumeManager(mpd_controller=None)
        manager.master_volume = 50
        
        success, message = manager.music_volume_down(amount=10)
        
        self.assertTrue(success)
        self.assertEqual(manager.master_volume, 40)
        self.assertIn("40", message)

    @patch('subprocess.run')
    def test_music_volume_down_floors_at_0(self, mock_run):
        """Test: Volume decrease floors at 0%"""
        mock_run.return_value.returncode = 0
        manager = VolumeManager(mpd_controller=None)
        manager.master_volume = 5
        
        success, message = manager.music_volume_down(amount=10)
        
        self.assertTrue(success)
        self.assertEqual(manager.master_volume, 0)

    @patch('subprocess.run')
    def test_volume_control_unavailable(self, mock_run):
        """Test: Volume operations return appropriate values when unavailable"""
        mock_run.return_value.returncode = 1  # pactl fails
        manager = VolumeManager(mpd_controller=None)
        
        success, message = manager.music_volume_up(10)
        self.assertFalse(success)
        self.assertIn("unavailable", message.lower())

    @patch('subprocess.run')
    def test_pulse_volume_parsing(self, mock_run):
        """Test: PulseAudio volume parsing from pactl output"""
        mock_run.return_value.returncode = 0
        manager = VolumeManager(mpd_controller=None)
        
        test_cases = [
            ("Volume: front-left: 26304 /  40% / -23.93 dB,   front-right: 26304 /  40%", 40),
            ("Volume: front-left: 32768 /  50% / -18.06 dB", 50),
            ("Volume: front-left: 49152 /  75% / -7.52 dB", 75),
        ]
        
        for output_line, expected_volume in test_cases:
            mock_run.return_value.stdout = output_line
            manager.master_volume = None  # Force fresh read
            
            volume = manager._get_pulse_volume()
            self.assertEqual(volume, expected_volume, f"Failed for: {output_line}")

    @patch('subprocess.run')
    def test_initialize_default_volume_order(self, mock_run):
        """Test: Master volume is set BEFORE MPD operations"""
        mock_run.return_value.returncode = 0
        call_order = []
        
        def track_calls(*args, **kwargs):
            if 'set-sink-volume' in str(args):
                call_order.append('pulse_set')
            result = Mock()
            result.returncode = 0
            return result
        
        mock_run.side_effect = track_calls
        
        # Track MPD calls
        def mpd_setvol(*args):
            call_order.append('mpd_setvol')
        
        self.mock_mpd.client.setvol = mpd_setvol
        
        manager = VolumeManager(mpd_controller=self.mock_mpd)
        manager.initialize_default_volume(default_volume=15)
        
        # Verify pulse is set before MPD
        pulse_idx = call_order.index('pulse_set') if 'pulse_set' in call_order else -1
        mpd_idx = call_order.index('mpd_setvol') if 'mpd_setvol' in call_order else len(call_order)
        
        self.assertLess(pulse_idx, mpd_idx, "Master volume should be set before MPD")


if __name__ == '__main__':
    unittest.main()
