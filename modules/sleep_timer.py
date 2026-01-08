"""
Sleep Timer Module

Reusable sleep timer with volume fade-out.
Can be used for sleep timers, meditation timers, alarms, etc.

Architecture: Callback-based design (no MPD dependencies)
"""

import threading
import time
import logging
from typing import Callable, Optional
from modules.logging_utils import setup_logger

logger = setup_logger(__name__)


class SleepTimer:
    """
    Reusable sleep timer with configurable fade-out.

    Thread-safe timer that fades volume over 30 seconds before stopping playback.
    Uses callbacks for flexibility (can control any audio system, not just MPD).
    """

    def __init__(
        self,
        get_volume_callback: Callable[[], int] = None,
        set_volume_callback: Callable[[int], None] = None,
        stop_callback: Callable[[], None] = None,
        fade_duration: int = 30,
        debug: bool = False
    ):
        """
        Initialize sleep timer.

        Args:
            get_volume_callback: Function to get current volume (0-100)
            set_volume_callback: Function to set volume (0-100)
            stop_callback: Function to stop playback
            fade_duration: Fade duration in seconds (default 30)
            debug: Enable debug logging
        """
        self._get_volume = get_volume_callback
        self._set_volume = set_volume_callback
        self._stop = stop_callback
        self._fade_duration = fade_duration

        # Threading state
        self._timer_thread: Optional[threading.Thread] = None
        self._cancel_event = threading.Event()
        self._lock = threading.Lock()

        self.debug = debug
        if debug:
            logger.setLevel(logging.DEBUG)

    def start(self, duration_minutes: int) -> bool:
        """
        Start sleep timer with fade-out.

        Args:
            duration_minutes: Timer duration in minutes

        Returns:
            True if timer started successfully
        """
        if duration_minutes <= 0:
            logger.warning(f"Invalid timer duration: {duration_minutes} minutes")
            return False

        def timer_worker():
            """Worker thread for sleep timer"""
            # Sleep for (duration - fade_duration)
            fade_start_delay = max(0, duration_minutes * 60 - self._fade_duration)

            if self._cancel_event.wait(timeout=fade_start_delay):
                logger.debug("Timer cancelled before fade started")
                return  # Cancelled

            # Start fade-out
            logger.info(f"Sleep timer: starting {self._fade_duration}s fade-out")

            try:
                # Get original volume
                original_vol = self._get_volume() if self._get_volume else 50
                logger.debug(f"Original volume: {original_vol}%")

                # Fade out over duration
                for i in range(self._fade_duration):
                    if self._cancel_event.is_set():
                        # Restore volume before cancelling
                        if self._set_volume:
                            self._set_volume(original_vol)
                        logger.info("Sleep timer cancelled during fade, volume restored")
                        return

                    # Calculate fade volume
                    fade_vol = int(original_vol * (1 - i / self._fade_duration))
                    if self._set_volume:
                        self._set_volume(fade_vol)

                    if self.debug and i % 5 == 0:  # Log every 5 seconds in debug mode
                        logger.debug(f"Fade progress: {i}/{self._fade_duration}s, volume: {fade_vol}%")

                    time.sleep(1)

                # Stop playback
                if self._stop:
                    self._stop()

                # Restore original volume for next playback
                if self._set_volume:
                    self._set_volume(original_vol)

                logger.info(f"Sleep timer completed: stopped playback, restored volume to {original_vol}%")

            except Exception as e:
                logger.error(f"Sleep timer error: {e}")

        # Atomic cancel+start operation (prevents race condition)
        with self._lock:
            # Cancel existing timer
            if self._timer_thread and self._timer_thread.is_alive():
                self._cancel_event.set()
                self._timer_thread.join(timeout=2.0)

                # Warn if thread didn't exit cleanly
                if self._timer_thread.is_alive():
                    logger.warning("Sleep timer thread did not exit cleanly (still running after 2s)")

            # Reset cancel event and start new timer
            self._cancel_event.clear()
            self._timer_thread = threading.Thread(
                target=timer_worker,
                daemon=True,
                name="SleepTimerWorker"
            )
            self._timer_thread.start()

        logger.info(f"Sleep timer started: {duration_minutes} minutes")
        return True

    def cancel(self) -> bool:
        """
        Cancel active sleep timer.

        Returns:
            True if timer was cancelled, False if no timer was active
        """
        with self._lock:
            if self._timer_thread and self._timer_thread.is_alive():
                self._cancel_event.set()
                self._timer_thread.join(timeout=1.0)
                logger.info("Sleep timer cancelled")
                return True

            logger.debug("No active sleep timer to cancel")
            return False

    def is_active(self) -> bool:
        """
        Check if sleep timer is currently active.

        Returns:
            True if timer is running
        """
        with self._lock:
            return self._timer_thread is not None and self._timer_thread.is_alive()

    def __del__(self):
        """Cleanup: cancel timer on destruction"""
        try:
            self.cancel()
        except Exception:
            pass  # Ignore errors during cleanup
