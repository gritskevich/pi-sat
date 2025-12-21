"""
MPD Controller - Music Player Daemon Control

Controls music playback via MPD (Music Player Daemon) using python-mpd2.
Implements persistent connection pattern with automatic reconnection.

Key Features:
- Play/pause/stop/skip/previous controls
- Volume control with ducking support
- Fuzzy music search in library
- Favorites playlist management (favorites.m3u)
- Sleep timer with volume fade-out
- Automatic reconnection on connection loss
- Singleton pattern (one connection instance)

MPD Connection:
- Default: localhost:6600
- Persistent connection with auto-reconnect
- Thread-safe operations
"""

import os
import time
import logging
import threading
from typing import Optional, List, Dict, Tuple
from contextlib import contextmanager

try:
    from mpd import MPDClient, ConnectionError as MPDConnectionError
except ImportError:
    MPDClient = None
    MPDConnectionError = Exception

# Import config
import config

from modules.music_library import MusicLibrary

# Logging
logger = logging.getLogger(__name__)


class MPDController:
    """
    Music Player Daemon controller with persistent connection.

    Singleton pattern - only one MPD connection across the application.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """Singleton pattern implementation"""
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        host: str = None,
        port: int = None,
        music_library: str = None,
        debug: bool = False
    ):
        """
        Initialize MPD Controller.

        Args:
            host: MPD server host (default: from config)
            port: MPD server port (default: from config)
            music_library: Music library path (default: from config)
            debug: Enable debug logging
        """
        # Only initialize once (singleton)
        if hasattr(self, '_initialized'):
            return

        self.host = host or config.MPD_HOST
        self.port = port or config.MPD_PORT
        self.music_library = music_library or config.MUSIC_LIBRARY
        self.debug = debug

        if MPDClient is None:
            raise RuntimeError("python-mpd2 not installed. Install with: pip install python-mpd2")

        self.client = MPDClient()
        self.client.timeout = 10  # 10 second timeout
        self.client.idletimeout = None

        self._connected = False
        self._music_library = MusicLibrary(
            library_path=self.music_library,
            fuzzy_threshold=config.FUZZY_MATCH_THRESHOLD,
            phonetic_enabled=True,
            phonetic_weight=0.6,
            debug=debug
        )

        # Sleep timer state
        self._sleep_timer_thread = None
        self._sleep_timer_cancel = threading.Event()

        # Volume ducking state
        self._original_volume = None
        self._ducking_active = False

        if debug:
            logger.setLevel(logging.DEBUG)

        self._initialized = True
        logger.info(f"MPD Controller initialized ({self.host}:{self.port})")

    def connect(self) -> bool:
        """
        Connect to MPD server.

        Returns:
            True if connected successfully
        """
        try:
            if not self._connected:
                self.client.connect(self.host, self.port)
                self._connected = True
                logger.info(f"Connected to MPD at {self.host}:{self.port}")
                if config.DEFAULT_SHUFFLE_MODE:
                    self.set_shuffle(True)
            return True

        except Exception as e:
            logger.error(f"Failed to connect to MPD: {e}")
            self._connected = False
            return False

    def disconnect(self):
        """Disconnect from MPD server"""
        try:
            if self._connected:
                self.client.close()
                self.client.disconnect()
                self._connected = False
                logger.info("Disconnected from MPD")
        except Exception as e:
            logger.warning(f"Error disconnecting from MPD: {e}")

    @contextmanager
    def _ensure_connection(self):
        """
        Context manager to ensure MPD connection.

        Automatically reconnects if connection lost.
        """
        try:
            if not self._connected:
                self.connect()
            yield
        except (MPDConnectionError, BrokenPipeError, ConnectionResetError) as e:
            logger.warning(f"MPD connection lost: {e}. Reconnecting...")
            self._connected = False
            self.connect()
            yield
        except Exception as e:
            logger.error(f"MPD operation failed: {e}")
            raise

    def get_status(self) -> Dict:
        """
        Get MPD player status.

        Returns:
            Dict with status info (state, volume, song, etc.)
        """
        with self._ensure_connection():
            status = self.client.status()
            current_song = self.client.currentsong()

            # Extract song name - prefer title, fallback to filename
            song_name = current_song.get('title', 'Unknown')
            if song_name == 'Unknown' and 'file' in current_song:
                # Extract name from filename
                file_path = current_song['file']
                song_name = os.path.splitext(os.path.basename(file_path))[0]
            
            # Extract artist - prefer artist tag, fallback to filename parsing
            artist_name = current_song.get('artist', 'Unknown')
            if artist_name == 'Unknown' and 'file' in current_song:
                # Try to extract from filename like "Artist - Song.mp3"
                file_path = current_song['file']
                filename = os.path.splitext(os.path.basename(file_path))[0]
                if ' - ' in filename:
                    artist_name = filename.split(' - ')[0]
            
            return {
                'state': status.get('state', 'stop'),  # play, pause, stop
                'volume': int(status.get('volume', 0)) if status.get('volume') not in (None, 'n/a', '-1') else None,
                'song': song_name,
                'artist': artist_name,
                'album': current_song.get('album', 'Unknown'),
            }

    def get_music_library(self):
        """Access MusicLibrary for query resolution."""
        return self._music_library

    def play(self, query: Optional[str] = None) -> Tuple[bool, str, Optional[float]]:
        """
        Play music.

        Args:
            query: Search query for song/artist (None to resume current)

        Returns:
            Tuple of (success, message, confidence)
            - confidence is None for resume, 0.0-1.0 for search results
        """
        with self._ensure_connection():
            # If no query, just resume current song
            if not query:
                self.client.play()
                status = self.get_status()
                return (True, f"Playing {status['song']}", None)

            # Search for music matching query - ALWAYS return best match
            logger.info(f"Song detection request: '{query}'")
            search_result = self.search_music_best(query)

            if not search_result:
                # Only happens if catalog is completely empty
                return (False, f"Music library is empty", 0.0)

            matched_file, confidence = search_result
            logger.info(f"Song detection answer: '{matched_file}' ({confidence:.2%})")

            # Clear playlist and add matched song
            self.client.clear()
            self.client.add(matched_file)
            self.client.play()

            logger.info(f"Playing: {matched_file} (confidence: {confidence:.2%})")
            return (True, f"Playing {query}", confidence)

    def pause(self) -> Tuple[bool, str]:
        """
        Pause playback.

        Returns:
            Tuple of (success, message)
        """
        with self._ensure_connection():
            self.client.pause(1)
            return (True, "Paused")

    def resume(self) -> Tuple[bool, str]:
        """
        Resume playback.

        Returns:
            Tuple of (success, message)
        """
        with self._ensure_connection():
            self.client.pause(0)
            status = self.get_status()
            return (True, f"Resuming {status['song']}")

    def stop(self) -> Tuple[bool, str]:
        """
        Stop playback.

        Returns:
            Tuple of (success, message)
        """
        with self._ensure_connection():
            self.client.stop()
            return (True, "Stopped")

    def next(self) -> Tuple[bool, str]:
        """
        Skip to next song.

        Returns:
            Tuple of (success, message)
        """
        with self._ensure_connection():
            # Check current position and playlist length
            status = self.client.status()
            current_pos_str = status.get('song', '0')
            playlist_length_str = status.get('playlistlength', '0')
            
            try:
                current_pos = int(current_pos_str)
                playlist_length = int(playlist_length_str)
            except (ValueError, TypeError):
                current_pos = 0
                playlist_length = 0
            
            # If at end of playlist, can't go next
            if playlist_length > 0 and current_pos >= playlist_length - 1:
                return (False, "Already at end of playlist")
            
            try:
                self.client.next()
            except Exception as e:
                logger.error(f"MPD next() failed: {e}")
                return (False, f"Could not skip to next: {e}")
            
            # Wait a moment for MPD to process
            time.sleep(0.1)
            
            # Get new status
            new_status = self.client.status()
            current = self.client.currentsong()
            
            # Check if actually playing
            if new_status.get('state') == 'stop':
                # Try to start playback
                try:
                    self.client.play()
                    time.sleep(0.1)
                    new_status = self.client.status()
                    current = self.client.currentsong()
                except:
                    pass
            
            # Extract song name
            song_name = current.get('title') or current.get('name', '')
            if not song_name and 'file' in current:
                # Extract from filename
                file_path = current['file']
                song_name = os.path.splitext(os.path.basename(file_path))[0]
            
            if not song_name:
                song_name = 'Unknown'
            
            return (True, f"Next: {song_name}")

    def previous(self) -> Tuple[bool, str]:
        """
        Go to previous song.

        Returns:
            Tuple of (success, message)
        """
        with self._ensure_connection():
            # Check current position
            status = self.client.status()
            current_pos = int(status.get('song', 0))
            
            # If at start of playlist, can't go previous
            if current_pos <= 0:
                return (False, "Already at start of playlist")
            
            self.client.previous()
            
            # Wait a moment for MPD to process
            time.sleep(0.1)
            
            # Get new status
            new_status = self.client.status()
            current = self.client.currentsong()
            
            # Check if actually playing
            if new_status.get('state') == 'stop':
                return (False, "Previous song unavailable or unplayable")
            
            song_name = current.get('title') or current.get('file', 'Unknown')
            if song_name == 'Unknown' and 'file' in current:
                # Try to extract name from filename
                song_name = os.path.splitext(os.path.basename(current['file']))[0]
            
            return (True, f"Previous: {song_name}")

    def volume_up(self, amount: int = 10) -> Tuple[bool, str]:
        """
        Increase volume.

        Args:
            amount: Volume increase amount (0-100)

        Returns:
            Tuple of (success, message)
        """
        with self._ensure_connection():
            status = self.client.status()
            current = int(status.get('volume', 50))

            # Respect max volume limit for kid safety
            max_vol = min(100, config.MAX_VOLUME)
            new_volume = min(max_vol, current + amount)

            self.client.setvol(new_volume)
            logger.info(f"Volume: {current} → {new_volume}")

            # Inform if we hit the limit
            if new_volume >= max_vol and max_vol < 100:
                return (True, f"Volume {new_volume}%. That's the maximum allowed")
            else:
                return (True, f"Volume {new_volume}%")

    def volume_down(self, amount: int = 10) -> Tuple[bool, str]:
        """
        Decrease volume.

        Args:
            amount: Volume decrease amount (0-100)

        Returns:
            Tuple of (success, message)
        """
        with self._ensure_connection():
            status = self.client.status()
            current = int(status.get('volume', 50))
            new_volume = max(0, current - amount)
            self.client.setvol(new_volume)
            logger.info(f"Volume: {current} → {new_volume}")
            return (True, f"Volume {new_volume}%")

    def duck_volume(self, duck_to: int = 20) -> bool:
        """
        Duck volume (temporarily lower for voice input).

        Args:
            duck_to: Target volume percentage during ducking

        Returns:
            True if ducked successfully
        """
        try:
            with self._ensure_connection():
                status = self.client.status()
                self._original_volume = int(status.get('volume', 50))
                self.client.setvol(duck_to)
                self._ducking_active = True
                logger.info(f"Volume ducked: {self._original_volume} → {duck_to}")
                return True
        except Exception as e:
            logger.error(f"Failed to duck volume: {e}")
            return False

    def restore_volume(self) -> bool:
        """
        Restore volume after ducking.

        Returns:
            True if restored successfully
        """
        try:
            if self._ducking_active and self._original_volume is not None:
                with self._ensure_connection():
                    self.client.setvol(self._original_volume)
                    logger.info(f"Volume restored: {self._original_volume}")
                    self._ducking_active = False
                    self._original_volume = None
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to restore volume: {e}")
            return False

    def search_music(self, query: str) -> Optional[Tuple[str, float]]:
        """
        Fuzzy search music library (respects threshold).

        Args:
            query: Search query (song name, artist, album)

        Returns:
            Tuple of (file_path, confidence) or None if not found above threshold
        """
        with self._ensure_connection():
            # Update MPD database first
            try:
                self.client.update()
            except Exception:
                pass  # Database update not critical

            # Load catalog from MPD if empty
            if self._music_library.is_empty():
                self._music_library.load_from_mpd(self.client)

            # Search using MusicLibrary
            result = self._music_library.search(query)

            return result

    def search_music_best(self, query: str) -> Optional[Tuple[str, float]]:
        """
        Fuzzy search music library - ALWAYS returns best match (ignores threshold).

        Use this when you want to play something even if confidence is low.
        Kid-friendly: better to play something than nothing!

        Args:
            query: Search query (song name, artist, album)

        Returns:
            Tuple of (file_path, confidence) or None only if catalog is empty
        """
        with self._ensure_connection():
            # Update MPD database first
            try:
                self.client.update()
            except Exception:
                pass  # Database update not critical

            # Load catalog from MPD if empty
            if self._music_library.is_empty():
                self._music_library.load_from_mpd(self.client)

            # Search using MusicLibrary (best match)
            result = self._music_library.search_best(query)

            return result

    def play_favorites(self) -> Tuple[bool, str]:
        """
        Play favorites playlist.

        Returns:
            Tuple of (success, message)
        """
        with self._ensure_connection():
            try:
                # Load favorites.m3u playlist
                self.client.clear()
                self.client.load('favorites')
                self.client.play()
                logger.info("Playing favorites playlist")
                return (True, "Playing your favorites")
            except Exception as e:
                logger.error(f"Failed to play favorites: {e}")
                return (False, "I couldn't find your favorites playlist")

    def add_to_favorites(self) -> Tuple[bool, str]:
        """
        Add current song to favorites playlist.

        Returns:
            Tuple of (success, message)
        """
        with self._ensure_connection():
            try:
                current = self.client.currentsong()

                if not current or 'file' not in current:
                    return (False, "No song is currently playing")

                file_path = current['file']

                # Add to favorites playlist
                self.client.playlistadd('favorites', file_path)

                song_name = current.get('title', os.path.basename(file_path))
                logger.info(f"Added to favorites: {song_name}")
                return (True, f"Added {song_name} to favorites")

            except Exception as e:
                logger.error(f"Failed to add to favorites: {e}")
                return (False, "I couldn't add this song to favorites")

    def set_sleep_timer(self, minutes: int) -> Tuple[bool, str]:
        """
        Set sleep timer with volume fade-out.

        Args:
            minutes: Duration in minutes

        Returns:
            Tuple of (success, message)
        """
        # Cancel existing timer
        if self._sleep_timer_thread and self._sleep_timer_thread.is_alive():
            self._sleep_timer_cancel.set()
            self._sleep_timer_thread.join(timeout=1)

        self._sleep_timer_cancel.clear()

        def sleep_timer_worker(duration_minutes):
            """Worker thread for sleep timer"""
            # Sleep for (duration - 30 seconds)
            fade_start = max(0, duration_minutes * 60 - 30)

            if self._sleep_timer_cancel.wait(timeout=fade_start):
                return  # Cancelled

            # Fade out over 30 seconds
            logger.info("Sleep timer: starting fade-out")

            try:
                with self._ensure_connection():
                    status = self.client.status()
                    original_vol = int(status.get('volume', 50))

                    for i in range(30):
                        if self._sleep_timer_cancel.is_set():
                            return  # Cancelled

                        fade_vol = int(original_vol * (1 - i / 30))
                        self.client.setvol(fade_vol)
                        time.sleep(1)

                    # Stop playback
                    self.client.stop()
                    logger.info("Sleep timer: stopped playback")

            except Exception as e:
                logger.error(f"Sleep timer error: {e}")

        # Start timer thread
        self._sleep_timer_thread = threading.Thread(
            target=sleep_timer_worker,
            args=(minutes,),
            daemon=True
        )
        self._sleep_timer_thread.start()

        logger.info(f"Sleep timer set: {minutes} minutes")
        return (True, f"I'll stop playing in {minutes} minutes")

    def cancel_sleep_timer(self) -> bool:
        """
        Cancel active sleep timer.

        Returns:
            True if timer was cancelled
        """
        if self._sleep_timer_thread and self._sleep_timer_thread.is_alive():
            self._sleep_timer_cancel.set()
            self._sleep_timer_thread.join(timeout=1)
            logger.info("Sleep timer cancelled")
            return True
        return False

    def set_repeat(self, mode: str) -> Tuple[bool, str]:
        """
        Set repeat mode.

        Args:
            mode: 'off', 'single', or 'playlist'

        Returns:
            Tuple of (success, message)
        """
        with self._ensure_connection():
            try:
                if mode == 'off':
                    self.client.repeat(0)
                    self.client.single(0)
                    msg = "Repeat off"
                elif mode == 'single':
                    self.client.repeat(1)
                    self.client.single(1)
                    msg = "Repeating current song"
                elif mode == 'playlist':
                    self.client.repeat(1)
                    self.client.single(0)
                    msg = "Repeating playlist"
                else:
                    return (False, f"Unknown repeat mode: {mode}")

                logger.info(f"Repeat mode set: {mode}")
                return (True, msg)

            except Exception as e:
                logger.error(f"Failed to set repeat mode: {e}")
                return (False, f"Could not set repeat mode")

    def toggle_shuffle(self) -> Tuple[bool, str]:
        """
        Toggle shuffle mode on/off.

        Returns:
            Tuple of (success, message)
        """
        with self._ensure_connection():
            try:
                status = self.client.status()
                current_shuffle = status.get('random', '0') == '1'

                # Toggle
                new_shuffle = not current_shuffle
                self.client.random(1 if new_shuffle else 0)

                msg = "Shuffle on" if new_shuffle else "Shuffle off"
                logger.info(f"Shuffle toggled: {new_shuffle}")
                return (True, msg)

            except Exception as e:
                logger.error(f"Failed to toggle shuffle: {e}")
                return (False, "Could not toggle shuffle")

    def set_shuffle(self, enabled: bool) -> Tuple[bool, str]:
        """
        Set shuffle mode explicitly.

        Args:
            enabled: True to enable shuffle, False to disable

        Returns:
            Tuple of (success, message)
        """
        with self._ensure_connection():
            try:
                self.client.random(1 if enabled else 0)
                msg = "Shuffle on" if enabled else "Shuffle off"
                logger.info(f"Shuffle set: {enabled}")
                return (True, msg)

            except Exception as e:
                logger.error(f"Failed to set shuffle: {e}")
                return (False, "Could not set shuffle")

    def add_to_queue(self, query: str, play_next: bool = False) -> Tuple[bool, str]:
        """
        Add song to queue.

        Args:
            query: Search query for song/artist
            play_next: If True, add as next song; if False, add to end of queue

        Returns:
            Tuple of (success, message)
        """
        with self._ensure_connection():
            try:
                # Search for music
                search_result = self.search_music(query)

                if not search_result:
                    return (False, f"I couldn't find '{query}' in your music library")

                matched_file, confidence = search_result

                if play_next:
                    # Add as next song (after current)
                    status = self.client.status()
                    current_pos = int(status.get('song', 0))
                    self.client.addid(matched_file, current_pos + 1)
                    msg = f"Playing {query} next"
                else:
                    # Add to end of queue
                    self.client.add(matched_file)
                    msg = f"Added {query} to queue"

                logger.info(f"Added to queue: {matched_file} (play_next={play_next})")
                return (True, msg)

            except Exception as e:
                logger.error(f"Failed to add to queue: {e}")
                return (False, "Could not add to queue")

    def clear_queue(self) -> Tuple[bool, str]:
        """
        Clear the current queue/playlist.

        Returns:
            Tuple of (success, message)
        """
        with self._ensure_connection():
            try:
                self.client.clear()
                logger.info("Queue cleared")
                return (True, "Queue cleared")

            except Exception as e:
                logger.error(f"Failed to clear queue: {e}")
                return (False, "Could not clear queue")

    def get_queue(self) -> List[Dict]:
        """
        Get current queue/playlist.

        Returns:
            List of songs in queue with metadata
        """
        with self._ensure_connection():
            try:
                playlist = self.client.playlistinfo()

                queue = []
                for song in playlist:
                    # Extract song info
                    title = song.get('title', 'Unknown')
                    if title == 'Unknown' and 'file' in song:
                        title = os.path.splitext(os.path.basename(song['file']))[0]

                    artist = song.get('artist', 'Unknown')
                    if artist == 'Unknown' and 'file' in song:
                        filename = os.path.splitext(os.path.basename(song['file']))[0]
                        if ' - ' in filename:
                            artist = filename.split(' - ')[0]

                    queue.append({
                        'title': title,
                        'artist': artist,
                        'file': song.get('file', '')
                    })

                return queue

            except Exception as e:
                logger.error(f"Failed to get queue: {e}")
                return []

    def get_queue_length(self) -> int:
        """
        Get number of songs in queue.

        Returns:
            Number of songs in queue
        """
        with self._ensure_connection():
            try:
                status = self.client.status()
                return int(status.get('playlistlength', 0))
            except Exception as e:
                logger.error(f"Failed to get queue length: {e}")
                return 0


def main():
    """Test MPD Controller"""
    import logging
    logging.basicConfig(level=logging.INFO)

    controller = MPDController(debug=True)

    print("MPD Controller Test\n")
    print("=" * 60)

    # Test connection
    print("\n1. Testing connection...")
    if controller.connect():
        print("  ✓ Connected to MPD")
    else:
        print("  ✗ Failed to connect")
        return

    # Test status
    print("\n2. Getting status...")
    status = controller.get_status()
    print(f"  State: {status['state']}")
    print(f"  Volume: {status['volume']}%")
    print(f"  Song: {status['song']}")
    print(f"  Artist: {status['artist']}")

    # Test search
    print("\n3. Testing music search...")
    test_queries = ["Frozen", "Beatles", "hey jude"]
    for query in test_queries:
        result = controller.search_music(query)
        if result:
            file_path, confidence = result
            print(f"  '{query}' → {os.path.basename(file_path)} ({confidence:.2%})")
        else:
            print(f"  '{query}' → No match")

    # Disconnect
    print("\n4. Disconnecting...")
    controller.disconnect()
    print("  ✓ Disconnected")


if __name__ == '__main__':
    main()
