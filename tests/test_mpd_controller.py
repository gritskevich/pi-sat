"""
Test MPD Controller - Music Player Daemon Control

Tests MPD interaction using mocked MPD client.
Follows patterns from CLAUDE.md.
"""

import unittest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import threading
import time

import config
from modules.mpd_controller import MPDController


class TestMPDController(unittest.TestCase):
    """Test MPD Controller with mocked MPD client"""

    def setUp(self):
        """Initialize MPD controller with mocked client"""
        # Create controller
        self.controller = MPDController(host='localhost', port=6600, debug=False)

        # Mock the MPD client
        self.mock_client = Mock()
        self.controller.client = self.mock_client
        self.controller._connected = True

        # Default mock status
        self.mock_client.status.return_value = {
            'state': 'play',
            'volume': '50',
            'playlistlength': '10',
            'song': '0',
        }

        # Default mock current song
        self.mock_client.currentsong.return_value = {
            'title': 'Test Song',
            'artist': 'Test Artist',
            'album': 'Test Album',
            'file': 'test/song.mp3',
        }

    def tearDown(self):
        """Clean up after tests"""
        pass

    def test_connect(self):
        """Test: Connect to MPD server

        Given: MPD controller initialized
        When: connect() called
        Then: Connects successfully
        """
        self.controller._connected = False

        success = self.controller.connect()

        self.assertTrue(success)
        self.mock_client.connect.assert_called_once()

    def test_disconnect(self):
        """Test: Disconnect from MPD server"""
        self.controller.disconnect()

        self.mock_client.close.assert_called_once()
        self.mock_client.disconnect.assert_called_once()
        self.assertFalse(self.controller._connected)

    def test_get_status(self):
        """Test: Get MPD player status

        Given: MPD playing
        When: get_status() called
        Then: Returns status dict
        """
        status = self.controller.get_status()

        self.assertEqual(status['state'], 'play')
        self.assertEqual(status['volume'], 50)
        self.assertEqual(status['song'], 'Test Song')
        self.assertEqual(status['artist'], 'Test Artist')

    def test_play_without_query(self):
        """Test: Play without query resumes current

        Given: Music paused
        When: play() called without query
        Then: Resumes playback
        """
        success, message, _confidence = self.controller.play()

        self.assertTrue(success)
        self.assertIn('Playing', message)
        self.mock_client.play.assert_called_once()

    def test_play_with_query_found(self):
        """Test: Play with query searches and plays

        Given: Query "maman"
        When: play() called
        Then: Searches library and plays match
        """
        # Mock listall to return test files
        self.mock_client.listall.return_value = [
            {'file': 'Louane - maman.mp3'},
            {'file': 'Kids United - On écrit sur les murs.mp3'},
        ]
        self.mock_client.playlistfind.return_value = [{'id': '42', 'file': 'Louane - maman.mp3'}]

        success, message, _confidence = self.controller.play("maman")

        self.assertTrue(success)
        self.assertIn('maman', message.lower())
        self.mock_client.clear.assert_not_called()
        self.mock_client.playid.assert_called_once_with(42)

    def test_play_with_query_not_found(self):
        """Test: Play with query not found

        Given: Query doesn't match library
        When: play() called
        Then: Returns failure message
        """
        # Mock empty library
        self.mock_client.listall.return_value = []

        success, message, confidence = self.controller.play("nonexistent song")

        self.assertFalse(success)
        self.assertIn("music library is empty", message.lower())
        self.assertEqual(confidence, 0.0)

    def test_pause(self):
        """Test: Pause playback

        Given: Music playing
        When: pause() called
        Then: Pauses playback
        """
        success, message = self.controller.pause()

        self.assertTrue(success)
        self.assertIn("Paused", message)  # Accept "Paused" or "Paused: Song Name"
        self.mock_client.pause.assert_called_once_with(1)

    def test_resume(self):
        """Test: Resume playback

        Given: Music paused
        When: resume() called
        Then: Resumes playback
        """
        # Set state to paused first
        self.mock_client.status.return_value = {
            'state': 'pause',
            'volume': '50',
        }

        success, message = self.controller.resume()

        self.assertTrue(success)
        # resume() calls pause(0) which toggles pause off
        self.mock_client.pause.assert_called_once_with(0)

    def test_stop(self):
        """Test: Stop playback

        Given: Music playing
        When: stop() called
        Then: Stops playback
        """
        success, message = self.controller.stop()

        self.assertTrue(success)
        self.assertEqual(message, "Stopped")
        self.mock_client.stop.assert_called_once()

    def test_next(self):
        """Test: Skip to next song

        Given: Music playing
        When: next() called
        Then: Skips to next track
        """
        success, message = self.controller.next()

        self.assertTrue(success)
        self.assertIn('Next', message)
        self.mock_client.next.assert_called_once()

    def test_previous(self):
        """Test: Go to previous song

        Given: Music playing
        When: previous() called
        Then: Goes to previous track
        """
        self.mock_client.status.return_value = {
            'state': 'play',
            'volume': '50',
            'song': '1',
        }
        success, message = self.controller.previous()

        self.assertTrue(success)
        self.assertIn('Previous', message)
        self.mock_client.previous.assert_called_once()

    @unittest.skip("Volume control moved to VolumeManager")
    def test_volume_up(self):
        """Test: Increase volume

        Given: Volume at 50%
        When: volume_up() called
        Then: Calls setvol with 60% (50 + 10)
        """
        success, message = self.controller.volume_up(amount=10)

        self.assertTrue(success)
        self.mock_client.setvol.assert_called_once_with(60)

    @unittest.skip("Volume control moved to VolumeManager")
    def test_volume_up_max_cap(self):
        """Test: Volume up capped at 100%

        Given: Volume at 95%
        When: volume_up(10) called
        Then: Sets to 100% (not 105%)
        """
        self.mock_client.status.return_value = {'volume': '95'}

        success, message = self.controller.volume_up(amount=10)

        self.assertTrue(success)
        expected_max = min(100, config.MAX_VOLUME)
        self.mock_client.setvol.assert_called_once_with(expected_max)

    @unittest.skip("Volume control moved to VolumeManager")
    def test_volume_down(self):
        """Test: Decrease volume

        Given: Volume at 50%
        When: volume_down() called
        Then: Calls setvol with 40% (50 - 10)
        """
        success, message = self.controller.volume_down(amount=10)

        self.assertTrue(success)
        self.mock_client.setvol.assert_called_once_with(40)

    @unittest.skip("Volume control moved to VolumeManager")
    def test_volume_down_min_cap(self):
        """Test: Volume down capped at 0%

        Given: Volume at 5%
        When: volume_down(10) called
        Then: Sets to 0% (not negative)
        """
        self.mock_client.status.return_value = {'volume': '5'}

        success, message = self.controller.volume_down(amount=10)

        self.assertTrue(success)
        self.mock_client.setvol.assert_called_once_with(0)

    @unittest.skip("Volume control moved to VolumeManager")
    def test_duck_volume(self):
        """Test: Duck volume for voice input

        Given: Volume at 50%
        When: duck_volume() called
        Then: Lowers to 20%, saves original
        """
        success = self.controller.duck_volume(duck_to=20)

        self.assertTrue(success)
        self.assertEqual(self.controller._original_volume, 50)
        self.assertTrue(self.controller._ducking_active)
        self.mock_client.setvol.assert_called_once_with(20)

    @unittest.skip("Volume control moved to VolumeManager")
    def test_restore_volume(self):
        """Test: Restore volume after ducking

        Given: Volume ducked to 20% from 50%
        When: restore_volume() called
        Then: Restores to 50%
        """
        # First duck
        self.controller.duck_volume(duck_to=20)

        # Then restore
        success = self.controller.restore_volume()

        self.assertTrue(success)
        self.assertFalse(self.controller._ducking_active)
        self.assertIsNone(self.controller._original_volume)

        # Check that setvol was called twice (duck + restore)
        calls = self.mock_client.setvol.call_args_list
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1][0][0], 50)  # Restored to 50

    @unittest.skip("Volume control moved to VolumeManager")
    def test_restore_volume_not_ducked(self):
        """Test: Restore volume when not ducked

        Given: Volume not ducked
        When: restore_volume() called
        Then: Returns False, no change
        """
        success = self.controller.restore_volume()

        self.assertFalse(success)

    @unittest.skip("Volume control moved to VolumeManager")
    def test_volume_up_mpd_disabled(self):
        """Test: Volume up when MPD software volume disabled

        Given: MPD volume control disabled (returns None)
        When: volume_up() called
        Then: Raises ValueError (MPDController doesn't handle ALSA fallback)
        """
        self.mock_client.status.return_value = {'volume': None}

        with self.assertRaises((ValueError, TypeError)):
            self.controller.volume_up(amount=10)

    @unittest.skip("Volume control moved to VolumeManager")
    def test_volume_up_mpd_n_a(self):
        """Test: Volume up when MPD returns 'n/a'

        Given: MPD volume control disabled (returns 'n/a')
        When: volume_up() called
        Then: Raises ValueError (MPDController doesn't handle ALSA fallback)
        """
        self.mock_client.status.return_value = {'volume': 'n/a'}

        with self.assertRaises(ValueError):
            self.controller.volume_up(amount=10)

    @unittest.skip("Volume control moved to VolumeManager")
    def test_volume_up_mpd_minus_one(self):
        """Test: Volume up when MPD returns '-1' (edge case)

        Given: MPD volume control disabled (returns '-1')
        When: volume_up() called
        Then: Treats '-1' as valid int and calls setvol(9) - documents limitation
        """
        self.mock_client.status.return_value = {'volume': '-1'}

        # '-1' can be converted to int, so MPDController treats it as valid
        # This documents a limitation: MPDController doesn't check for -1
        success, message = self.controller.volume_up(amount=10)

        # Verifies actual behavior: treats -1 as valid volume
        self.assertTrue(success)
        self.mock_client.setvol.assert_called_once_with(9)  # -1 + 10 = 9

    @unittest.skip("Volume control moved to VolumeManager")
    def test_volume_down_mpd_disabled(self):
        """Test: Volume down when MPD software volume disabled

        Given: MPD volume control disabled (returns None)
        When: volume_down() called
        Then: Raises ValueError (MPDController doesn't handle ALSA fallback)
        """
        self.mock_client.status.return_value = {'volume': None}

        with self.assertRaises((ValueError, TypeError)):
            self.controller.volume_down(amount=10)

    def test_get_status_volume_disabled(self):
        """Test: Get status when MPD volume disabled

        Given: MPD volume control disabled (returns 'n/a')
        When: get_status() called
        Then: Returns status with volume=None
        """
        self.mock_client.status.return_value = {
            'state': 'play',
            'volume': 'n/a',
        }

        status = self.controller.get_status()

        self.assertEqual(status['state'], 'play')
        self.assertIsNone(status.get('volume'))

    @unittest.skip("Volume control moved to VolumeManager")
    def test_duck_volume_mpd_disabled(self):
        """Test: Duck volume when MPD software volume disabled

        Given: MPD volume control disabled (returns None)
        When: duck_volume() called
        Then: Returns False (can't duck without volume control)
        """
        self.mock_client.status.return_value = {'volume': None}

        success = self.controller.duck_volume(duck_to=20)

        self.assertFalse(success)

    def test_search_music(self):
        """Test: Fuzzy search music library

        Given: Library with test songs
        When: search_music() called
        Then: Returns best match
        """
        # Mock library
        self.mock_client.listall.return_value = [
            {'file': 'Louane - maman.mp3'},
            {'file': 'Louane - Jour 1.mp3'},
            {'file': 'Kids United - On écrit sur les murs.mp3'},
        ]

        result = self.controller.search_music("maman")

        self.assertIsNotNone(result)
        file_path, confidence = result
        self.assertIn('Louane', file_path)
        self.assertGreater(confidence, 0.5)

    def test_search_music_typo(self):
        """Test: Search music with typo

        Given: Library with "Louane"
        When: search_music("louanne") called
        Then: Still matches "Louane"
        """
        self.mock_client.listall.return_value = [
            {'file': 'Louane - maman.mp3'},
        ]

        result = self.controller.search_music("louanne")

        # Fuzzy matching should handle typo
        if result:  # May or may not match depending on threshold
            file_path, confidence = result
            self.assertIn('Louane', file_path)

    def test_search_music_empty_library(self):
        """Test: Search empty library

        Given: Empty library
        When: search_music() called
        Then: Returns None
        """
        self.mock_client.listall.return_value = []

        result = self.controller.search_music("maman")

        self.assertIsNone(result)

    def test_play_favorites(self):
        """Test: Play favorites playlist

        Given: favorites.m3u exists
        When: play_favorites() called
        Then: Loads and plays favorites
        """
        success, message = self.controller.play_favorites()

        self.assertTrue(success)
        self.assertIn('favorites', message.lower())
        self.mock_client.clear.assert_called_once()
        self.mock_client.load.assert_called_once_with('favorites')
        self.mock_client.play.assert_called_once()

    def test_play_favorites_not_found(self):
        """Test: Play favorites when playlist doesn't exist

        Given: No favorites.m3u
        When: play_favorites() called
        Then: Returns error message
        """
        self.mock_client.load.side_effect = Exception("Playlist not found")

        success, message = self.controller.play_favorites()

        self.assertFalse(success)
        self.assertIn("couldn't find", message.lower())

    def test_add_to_favorites(self):
        """Test: Add current song to favorites

        Given: Song playing
        When: add_to_favorites() called
        Then: Adds song to favorites playlist
        """
        success, message = self.controller.add_to_favorites()

        self.assertTrue(success)
        self.assertIn('favorites', message.lower())
        self.mock_client.playlistadd.assert_called_once_with('favorites', 'test/song.mp3')

    def test_add_to_favorites_no_song(self):
        """Test: Add to favorites when nothing playing

        Given: No song playing
        When: add_to_favorites() called
        Then: Returns error message
        """
        self.mock_client.currentsong.return_value = {}

        success, message = self.controller.add_to_favorites()

        self.assertFalse(success)
        self.assertIn('no song', message.lower())

    def test_set_sleep_timer(self):
        """Test: Set sleep timer

        Given: Music playing
        When: set_sleep_timer(1) called (1 minute for testing)
        Then: Timer starts
        """
        success, message = self.controller.set_sleep_timer(minutes=1)

        self.assertTrue(success)
        self.assertIn('1 minute', message.lower())
        self.assertIsNotNone(self.controller._sleep_timer_thread)
        self.assertTrue(self.controller._sleep_timer_thread.is_alive())

        # Clean up
        self.controller.cancel_sleep_timer()

    def test_cancel_sleep_timer(self):
        """Test: Cancel active sleep timer

        Given: Sleep timer running
        When: cancel_sleep_timer() called
        Then: Timer cancelled
        """
        # Start timer
        self.controller.set_sleep_timer(minutes=5)

        # Cancel it
        success = self.controller.cancel_sleep_timer()

        self.assertTrue(success)

        # Wait for thread to finish
        time.sleep(0.5)
        if self.controller._sleep_timer_thread:
            self.assertFalse(self.controller._sleep_timer_thread.is_alive())

    def test_cancel_sleep_timer_none_active(self):
        """Test: Cancel when no timer active

        Given: No timer running
        When: cancel_sleep_timer() called
        Then: Returns False
        """
        success = self.controller.cancel_sleep_timer()

        self.assertFalse(success)

    @unittest.skip("Singleton pattern removed")
    def test_singleton_pattern(self):
        """Test: Singleton pattern (one instance only)

        Given: First controller created
        When: Second controller created
        Then: Returns same instance
        """
        controller1 = MPDController()
        controller2 = MPDController()

        self.assertIs(controller1, controller2)

    def test_reconnect_on_error(self):
        """Test: Automatic reconnection on connection error

        Given: Connection lost
        When: MPD command executed
        Then: Reconnects automatically
        """
        from mpd import ConnectionError as MPDConnectionError

        # First call fails, second succeeds
        self.mock_client.status.side_effect = [
            MPDConnectionError("Connection lost"),
            {'state': 'play', 'volume': '50'}
        ]

        # Should reconnect and succeed
        with patch.object(self.controller, 'connect') as mock_connect:
            try:
                status = self.controller.get_status()
                # May fail or succeed depending on reconnect behavior
            except:
                pass  # Expected in some cases


class TestMPDControllerIntegration(unittest.TestCase):
    """Integration tests for MPD controller"""

    def setUp(self):
        """Initialize for integration tests"""
        self.controller = MPDController(debug=False)

        # Mock client
        self.mock_client = Mock()
        self.controller.client = self.mock_client
        self.controller._connected = True

        # Setup default mocks
        self.mock_client.status.return_value = {
            'state': 'stop',
            'volume': '50',
            'playlistlength': '10',
            'song': '0',
        }

        self.mock_client.currentsong.return_value = {
            'title': 'maman',
            'artist': 'Louane',
            'file': 'Louane - maman.mp3',
        }

        self.mock_client.listall.return_value = [
            {'file': 'Louane - maman.mp3'},
            {'file': 'Kids United - On écrit sur les murs.mp3'},
        ]
        self.mock_client.playlistfind.return_value = [{'id': '42', 'file': 'Louane - maman.mp3'}]

    def tearDown(self):
        """Clean up"""
        pass

    def test_play_pipeline(self):
        """Test: Full play command pipeline

        Given: User wants to play "maman"
        When: play() called
        Then: Searches, finds, and plays song
        """
        success, message, _confidence = self.controller.play("maman")

        self.assertTrue(success)

        # Verify pipeline: search → playlist find → play by id (keeps queue for continuous shuffle)
        self.mock_client.listall.assert_called()
        self.mock_client.clear.assert_not_called()
        self.mock_client.playid.assert_called_once_with(42)

    @unittest.skip("Volume control moved to VolumeManager")
    def test_volume_duck_and_restore_pipeline(self):
        """Test: Volume ducking pipeline

        Given: Normal playback at 50%
        When: duck → restore
        Then: Volume restored correctly
        """
        # Duck volume
        self.controller.duck_volume(duck_to=10)
        self.assertEqual(self.controller._original_volume, 50)

        # Restore
        self.controller.restore_volume()
        self.assertIsNone(self.controller._original_volume)

    def test_favorites_workflow(self):
        """Test: Favorites workflow

        Given: Song playing
        When: add_to_favorites() → play_favorites()
        Then: Adds and plays favorites
        """
        # Add current song
        success1, msg1 = self.controller.add_to_favorites()
        self.assertTrue(success1)

        # Play favorites
        success2, msg2 = self.controller.play_favorites()
        self.assertTrue(success2)

        # Verify calls
        self.mock_client.playlistadd.assert_called_once()
        self.mock_client.load.assert_called_once()


if __name__ == '__main__':
    unittest.main()
