"""
MPD Controller - Music Player Daemon Control

Controls music playback via MPD (Music Player Daemon) using python-mpd2.
Implements persistent connection pattern with automatic reconnection.

Key Features:
- Play/pause/stop/skip/previous controls
- Fuzzy music search in library
- Favorites playlist management (favorites.m3u)
- Sleep timer with volume fade-out
- Automatic reconnection on connection loss

MPD Connection:
- Default: localhost:6600
- Persistent connection with auto-reconnect
- Thread-safe operations

Note: Volume control is handled by VolumeManager (PulseAudio sink).
MPD software volume is set to 100% at startup and never changed.
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
    """

    def __init__(
        self,
        host: str = None,
        port: int = None,
        music_library: str = None,  # DEPRECATED: Use music_library_instance instead
        music_library_instance: 'MusicLibrary' = None,  # NEW: Inject MusicLibrary
        debug: bool = False
    ):
        """
        Initialize MPD Controller.

        Args:
            host: MPD server host (default: from config)
            port: MPD server port (default: from config)
            music_library: Music library path (default: from config) - DEPRECATED, use music_library_instance
            music_library_instance: Pre-configured MusicLibrary instance (recommended for dependency injection)
            debug: Enable debug logging

        Note:
            Prefer using music_library_instance for dependency injection (better testability).
            If not provided, MusicLibrary will be created internally (backward compatible).
        """
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

        # Use injected MusicLibrary or create internally (backward compatible)
        if music_library_instance is not None:
            self._music_library = music_library_instance
        else:
            # Fallback: create internally
            self._music_library = MusicLibrary(
                library_path=self.music_library,
                fuzzy_threshold=config.FUZZY_MATCH_THRESHOLD,
                phonetic_enabled=True,
                phonetic_weight=config.PHONETIC_WEIGHT,
                debug=debug
            )

        # Sleep timer state
        self._sleep_timer_thread = None
        self._sleep_timer_cancel = threading.Event()
        self._sleep_timer_lock = threading.Lock()  # Thread-safe sleep timer management

        if debug:
            logger.setLevel(logging.DEBUG)

        logger.info(f"MPD Controller initialized ({self.host}:{self.port})")

    def connect(self) -> bool:
        """
        Connect to MPD server.

        Returns:
            True if connected successfully
        """
        try:
            if not self._connected:
                try:
                    self.client.connect(self.host, self.port)
                except (MPDConnectionError, ConnectionError) as conn_err:
                    # Handle "Already connected" case (client connection persisted despite flag reset)
                    if "Already connected" in str(conn_err):
                        logger.debug("MPD client already connected, reusing connection")
                    else:
                        raise  # Re-raise other connection errors

                self._connected = True
                logger.info(f"Connected to MPD at {self.host}:{self.port}")
                # Apply default playback modes (does not alter the current song/volume)
                self.set_shuffle(bool(getattr(config, "DEFAULT_SHUFFLE_MODE", False)))
                default_repeat = getattr(config, "DEFAULT_REPEAT_MODE", None)
                if default_repeat:
                    self.set_repeat(default_repeat)

                # Update MPD database to pick up new files, then load catalog
                try:
                    self.client.update()
                except Exception:
                    pass  # Update is best-effort

                if self._music_library.is_empty():
                    try:
                        count = self._music_library.load_from_mpd(self.client)
                        logger.debug(f"Loaded {count} songs from MPD database")
                    except Exception as e:
                        logger.warning(f"Failed to load music catalog: {e}")

                # Ensure we have a real queue for continuous shuffle mode.
                # Important: only appends when the queue is empty/tiny, so restarts won't disrupt playback.
                if getattr(config, "DEFAULT_SHUFFLE_MODE", False):
                    try:
                        self._ensure_queue_seeded(min_songs=2)
                    except Exception as e:
                        logger.warning(f"Failed to seed shuffle queue: {e}")
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
        if not self._connected:
            self.connect()
        try:
            yield
        except (MPDConnectionError, ConnectionError, OSError) as e:
            # Only log if we haven't already started reconnecting (avoid double logging)
            if self._connected:
                logger.warning(f"MPD connection lost: {e}. Reconnecting...")
                self._connected = False
                self.connect()
            raise  # Let caller retry if needed

    def _ensure_queue_seeded(self, min_songs: int = 2) -> bool:
        """
        Ensure MPD has a non-trivial queue to support continuous shuffle play.

        - Does not clear or restart playback.
        - Only adds songs when playlist is empty/tiny (e.g., after "play <song>" on old versions).
        """
        try:
            status = self.client.status()
            playlist_len = int(status.get('playlistlength', 0) or 0)
        except Exception:
            playlist_len = 0

        if playlist_len >= min_songs:
            return True

        # Ensure we have a catalog to seed from
        if self._music_library.is_empty():
            try:
                self._music_library.load_from_mpd(self.client)
            except Exception as e:
                logger.warning(f"Failed to load catalog for seeding: {e}")

        all_songs = self._music_library.get_all_songs()
        if not all_songs:
            return False

        # Avoid duplicates when the playlist is tiny (0/1 entries)
        existing_files = set()
        if playlist_len > 0:
            try:
                for item in self.client.playlistinfo():
                    file_path = item.get('file')
                    if file_path:
                        existing_files.add(file_path)
            except Exception:
                pass

        songs_to_add = [p for p in all_songs if p not in existing_files]
        if not songs_to_add:
            return True

        try:
            if hasattr(self.client, "command_list_ok_begin"):
                self.client.command_list_ok_begin()
                try:
                    for path in songs_to_add:
                        self.client.add(path)
                finally:
                    # Ensure command list is always closed to keep the connection usable.
                    self.client.command_list_end()
            else:
                for path in songs_to_add:
                    self.client.add(path)
        except Exception as e:
            logger.error(f"Failed to seed queue: {e}")
            return False

        logger.info(f"Seeded MPD queue: +{len(songs_to_add)} songs (total catalog={len(all_songs)})")
        return True

    def _find_playlist_song_id(self, file_path: str) -> Optional[int]:
        """Find a song id in the current playlist by exact file path."""
        try:
            matches = self.client.playlistfind('file', file_path)
            if not matches:
                return None
            song_id = matches[0].get('id')
            if song_id is None:
                return None
            return int(song_id)
        except Exception:
            return None

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
            query: Search query for song/artist, OR exact file path from validator (None to resume current)

        Returns:
            Tuple of (success, message, confidence)
            - confidence is None for resume, 0.0-1.0 for search results
        """
        with self._ensure_connection():
            # If no query, just resume current song
            if not query:
                # If queue is empty (fresh MPD), seed so "play" actually starts music.
                try:
                    self._ensure_queue_seeded(min_songs=1)
                except (ConnectionError, TimeoutError) as e:
                    logger.warning(f"Failed to seed queue (connection issue): {e}")
                    # Continue anyway - play will fail gracefully if queue is empty
                except Exception as e:
                    logger.error(f"Unexpected error seeding queue: {e}")
                    # Continue anyway - play will fail gracefully if queue is empty

                self.client.play()
                status = self.get_status()
                return (True, f"Playing {status['song']}", None)

            # Check if query is an exact file path (from validator) or a search query
            # File paths end with .mp3 and exist in the catalog
            if query.endswith('.mp3') and self._music_library.file_exists(query):
                # Direct file path from validator - use it directly, no search needed
                matched_file = query
                confidence = 1.0
                logger.info(f"🎵 Playing exact file: '{matched_file}'")
            else:
                # Search query - find best match
                logger.info(f"Song detection request: '{query}'")
                search_result = self.search_music_best(query)

                if not search_result:
                    # Only happens if catalog is completely empty
                    return (False, f"Music library is empty", 0.0)

                matched_file, confidence = search_result
                logger.info(f"Song detection answer: '{matched_file}' ({confidence:.2%})")

            # Keep a real shuffle queue so the next track is random (continuous shuffle by default).
            try:
                self._ensure_queue_seeded(min_songs=2)
            except Exception:
                pass

            song_id = self._find_playlist_song_id(matched_file)
            if song_id is None:
                try:
                    song_id = int(self.client.addid(matched_file))
                except Exception:
                    # Fallback for older MPD: add then find
                    self.client.add(matched_file)
                    song_id = self._find_playlist_song_id(matched_file)

            if song_id is None:
                logger.error("Failed to queue requested song in MPD")
                return (False, "Could not play that song", confidence)

            self.client.playid(song_id)

            # Get song details for better logging
            song_title = os.path.splitext(os.path.basename(matched_file))[0]
            logger.info(f"🎵 Now playing: {song_title}")
            logger.debug(f"   File: {matched_file} (confidence: {confidence:.2%})")
            return (True, f"Playing {query}", confidence)

    def pause(self) -> Tuple[bool, str]:
        """
        Pause playback (safe even if nothing is playing).

        Returns:
            Tuple of (success, message)
        """
        max_retries = 2
        for attempt in range(max_retries):
            try:
                with self._ensure_connection():
                    status = self.get_status()
                    if status['state'] in ('play', 'pause'):
                        self.client.pause(1)
                        song = status.get('song', 'unknown')
                        logger.info(f"⏸️  Paused: {song}")
                        return (True, f"Paused: {song}")
                    else:
                        logger.info("⏸️  Nothing playing, pause ignored")
                        return (True, "Nothing to pause")
            except (MPDConnectionError, ConnectionError, OSError) as e:
                if attempt < max_retries - 1:
                    logger.debug(f"⏸️  Pause connection error (retry {attempt+1}/{max_retries}): {e}")
                    self._connected = False
                    time.sleep(0.1)
                    continue
                else:
                    logger.warning(f"⏸️  Pause failed after {max_retries} retries (continuing anyway): {e}")
                    return (True, "Paused")  # Return success anyway - pause is best-effort
            except Exception as e:
                logger.warning(f"⏸️  Pause failed (continuing anyway): {e}")
                return (True, "Paused")  # Return success anyway - pause is best-effort

    def resume(self) -> Tuple[bool, str]:
        """
        Resume playback (safe even if nothing was paused).

        Returns:
            Tuple of (success, message)
        """
        try:
            with self._ensure_connection():
                status = self.get_status()
                if status['state'] == 'pause':
                    self.client.pause(0)
                    song = status.get('song', 'music')
                    logger.info(f"▶️  Resumed: {song}")
                    return (True, f"Resuming {song}")
                else:
                    logger.debug("Nothing paused, resume ignored")
                    return (True, "Nothing to resume")
        except Exception as e:
            logger.debug(f"Resume failed (not critical): {e}")
            return (True, "Resumed")  # Return success anyway - resume is best-effort

    def stop(self) -> Tuple[bool, str]:
        """
        Stop playback.

        Returns:
            Tuple of (success, message)
        """
        with self._ensure_connection():
            self.client.stop()
            logger.info("⏹️  Playback stopped")
            return (True, "Stopped")

    def next(self) -> Tuple[bool, str]:
        """
        Skip to next song.

        Returns:
            Tuple of (success, message)
        """
        with self._ensure_connection():
            # Ensure a real queue so "next" works after single-song requests.
            try:
                status = self.client.status()
                playlist_length = int(status.get('playlistlength', 0) or 0)
                current_state = status.get('state', 'stop')
            except Exception:
                playlist_length = None
                current_state = 'stop'

            if playlist_length is not None and playlist_length <= 1:
                try:
                    self._ensure_queue_seeded(min_songs=2)
                except Exception:
                    pass

            try:
                # If stopped, we need to start playing instead of calling next()
                # because MPD's next() requires active playback
                if current_state == 'stop':
                    if playlist_length == 0:
                        # Empty queue - seed and play
                        try:
                            self._ensure_queue_seeded(min_songs=1)
                        except Exception:
                            pass
                    # Start playing from the beginning (or continue where we left off)
                    self.client.play()
                elif playlist_length == 0:
                    # Queue empty but playing - shouldn't happen, but handle it
                    self.client.play()
                else:
                    # Normal case: skip to next song
                    self.client.next()
            except Exception as e:
                logger.error(f"MPD next() failed: {e}")
                return (False, f"Could not skip to next: {e}")

            # Wait a moment for MPD to process
            time.sleep(0.1)

            # Get new status
            new_status = self.client.status()
            current = self.client.currentsong()

            # Extract song name
            song_name = current.get('title') or current.get('name', '')
            if not song_name and 'file' in current:
                # Extract from filename
                file_path = current['file']
                song_name = os.path.splitext(os.path.basename(file_path))[0]

            if not song_name:
                song_name = 'Unknown'

            logger.info(f"🎵 Now playing: {song_name}")
            return (True, f"Next: {song_name}")

    def previous(self) -> Tuple[bool, str]:
        """
        Go to previous song.

        Returns:
            Tuple of (success, message)
        """
        with self._ensure_connection():
            # Check current position and state
            status = self.client.status()
            current_pos = int(status.get('song', 0))
            current_state = status.get('state', 'stop')

            # If stopped, start playing at current position instead of going previous
            if current_state == 'stop':
                try:
                    self.client.play()
                    time.sleep(0.1)
                    current = self.client.currentsong()
                    song_name = current.get('title') or current.get('file', 'Unknown')
                    if song_name == 'Unknown' and 'file' in current:
                        song_name = os.path.splitext(os.path.basename(current['file']))[0]
                    return (True, f"Playing: {song_name}")
                except Exception as e:
                    logger.error(f"MPD previous() failed to start playback: {e}")
                    return (False, "Could not start playback")

            # If at start of playlist, can't go previous
            if current_pos <= 0:
                return (False, "Already at start of playlist")

            try:
                self.client.previous()
            except Exception as e:
                logger.error(f"MPD previous() failed: {e}")
                return (False, f"Could not go to previous: {e}")

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

            logger.info(f"🎵 Now playing: {song_name}")
            return (True, f"Previous: {song_name}")

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
                logger.info("⭐ Playing favorites playlist")
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
                logger.info(f"⭐ Added to favorites: {song_name}")
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

        # Atomic cancel+start operation (prevents race condition)
        with self._sleep_timer_lock:
            # Cancel existing timer
            if self._sleep_timer_thread and self._sleep_timer_thread.is_alive():
                self._sleep_timer_cancel.set()
                self._sleep_timer_thread.join(timeout=2.0)  # Longer timeout for graceful exit

                # Warn if thread didn't exit cleanly
                if self._sleep_timer_thread.is_alive():
                    logger.warning("Sleep timer thread did not exit cleanly (still running after 2s)")
                    # Thread will eventually exit on next cancel check

            # Reset cancel event and start new timer (still holding lock)
            self._sleep_timer_cancel.clear()
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
        with self._sleep_timer_lock:
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

                logger.info(f"🔁 Repeat mode: {mode}")
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
                logger.info(f"🔀 Shuffle: {msg}")
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
                logger.info(f"🔀 Shuffle: {msg}")
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
