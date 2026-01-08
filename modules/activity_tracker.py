"""
Activity Tracker Module

Tracks daily listening time and enforces time limits for kid-safe usage.
Simple, file-based persistence following KISS principles.
"""

import json
import threading
from datetime import datetime, date
from pathlib import Path
from typing import Optional, Dict, Any
from modules.logging_utils import setup_logger

logger = setup_logger(__name__)


class ActivityTracker:
    """
    Tracks music listening time and enforces daily limits.

    Design:
    - Tracks total listening time per day
    - Enforces configurable daily limit (e.g., 2 hours)
    - Persists data to ~/.pisat_usage.json
    - Automatic reset at midnight
    - Thread-safe
    """

    def __init__(
        self,
        daily_limit_minutes: int = 120,  # 2 hours default
        warning_minutes: int = 15,  # Warn when 15 min remain
        storage_path: Optional[str] = None,
        enabled: bool = True,
        debug: bool = False
    ):
        """
        Initialize activity tracker.

        Args:
            daily_limit_minutes: Maximum listening time per day (minutes)
            warning_minutes: Minutes remaining to trigger warning
            storage_path: Path to persistent storage file
            enabled: Enable time limit enforcement
            debug: Enable debug logging
        """
        self.daily_limit_minutes = daily_limit_minutes
        self.warning_minutes = warning_minutes
        self.enabled = enabled

        # Storage
        if storage_path is None:
            storage_path = str(Path.home() / '.pisat_usage.json')
        self.storage_path = Path(storage_path)

        # State
        self._lock = threading.Lock()
        self._listening_start: Optional[datetime] = None
        self._today_minutes: int = 0
        self._last_warning_given = False
        self._load_state()

        if debug:
            import logging
            logger.setLevel(logging.DEBUG)

        logger.info(
            f"ActivityTracker initialized: "
            f"limit={daily_limit_minutes}min/day, "
            f"enabled={enabled}"
        )

    def start_listening(self):
        """Mark start of listening session"""
        with self._lock:
            # Check for day change and reset if needed
            self._check_reset()

            if self._listening_start is None:
                self._listening_start = datetime.now()
                logger.debug("Listening session started")

    def stop_listening(self):
        """Mark end of listening session and update total time"""
        with self._lock:
            if self._listening_start is None:
                return

            # Calculate session duration
            session_end = datetime.now()
            duration_seconds = (session_end - self._listening_start).total_seconds()
            duration_minutes = int(duration_seconds / 60)

            # Update today's total
            self._today_minutes += duration_minutes
            self._listening_start = None

            logger.debug(
                f"Listening session ended: +{duration_minutes}min, "
                f"total today={self._today_minutes}min"
            )

            # Persist state
            self._save_state()

    def is_limit_reached(self) -> bool:
        """
        Check if daily limit has been reached.

        Returns:
            True if limit exceeded
        """
        if not self.enabled:
            return False

        with self._lock:
            self._check_reset()

            # Include current session time
            total_minutes = self._get_total_minutes()

            exceeded = total_minutes >= self.daily_limit_minutes

            if exceeded:
                logger.debug(
                    f"Daily limit reached: {total_minutes}/{self.daily_limit_minutes}min"
                )

            return exceeded

    def should_warn_limit(self) -> bool:
        """
        Check if we should warn about approaching limit.

        Returns:
            True if warning should be given (and hasn't been given yet)
        """
        if not self.enabled or self._last_warning_given:
            return False

        with self._lock:
            remaining = self.get_remaining_minutes()

            if remaining is not None and 0 < remaining <= self.warning_minutes:
                self._last_warning_given = True
                logger.debug(f"Warning triggered: {remaining}min remaining")
                return True

            return False

    def get_remaining_minutes(self) -> Optional[int]:
        """
        Get remaining listening time today.

        Returns:
            Minutes remaining, or None if limit disabled or exceeded
        """
        if not self.enabled:
            return None

        with self._lock:
            self._check_reset()
            total_minutes = self._get_total_minutes()
            remaining = self.daily_limit_minutes - total_minutes

            return remaining if remaining > 0 else 0

    def get_usage_today(self) -> int:
        """Get total listening time today (minutes)"""
        with self._lock:
            self._check_reset()
            return self._get_total_minutes()

    def get_limit_message(self, language: str = 'fr') -> str:
        """Get limit reached message"""
        if language == 'fr':
            return (
                f"Tu as écouté assez de musique aujourd'hui ({self.daily_limit_minutes} minutes). "
                "Tu pourras réécouter demain !"
            )
        else:
            return (
                f"You've listened to enough music today ({self.daily_limit_minutes} minutes). "
                "You can listen again tomorrow!"
            )

    def get_warning_message(self, language: str = 'fr') -> str:
        """Get approaching limit warning message"""
        remaining = self.get_remaining_minutes() or 0
        if language == 'fr':
            return f"Attention, il te reste {remaining} minutes de musique aujourd'hui."
        else:
            return f"Heads up, you have {remaining} minutes of music left today."

    def reset_today(self):
        """Manually reset today's usage (for testing or manual reset)"""
        with self._lock:
            self._today_minutes = 0
            self._listening_start = None
            self._last_warning_given = False
            self._save_state()
            logger.info("Usage reset for today")

    def _get_total_minutes(self) -> int:
        """Get total minutes including current session (internal, requires lock)"""
        total = self._today_minutes

        # Add current session if active
        if self._listening_start:
            session_seconds = (datetime.now() - self._listening_start).total_seconds()
            total += int(session_seconds / 60)

        return total

    def _check_reset(self):
        """Check if day has changed and reset if needed (internal, requires lock)"""
        state = self._load_state_dict()
        last_date_str = state.get('date')

        today_str = date.today().isoformat()

        if last_date_str != today_str:
            logger.info(
                f"New day detected: {last_date_str} → {today_str}, resetting usage"
            )
            self._today_minutes = 0
            self._listening_start = None
            self._last_warning_given = False
            self._save_state()

    def _load_state(self):
        """Load state from persistent storage"""
        state = self._load_state_dict()
        today_str = date.today().isoformat()

        if state.get('date') == today_str:
            self._today_minutes = state.get('minutes', 0)
            logger.debug(f"Loaded state: {self._today_minutes}min today")
        else:
            self._today_minutes = 0
            logger.debug("No state for today, starting fresh")

    def _load_state_dict(self) -> Dict[str, Any]:
        """Load state dictionary from file"""
        if not self.storage_path.exists():
            return {}

        try:
            with open(self.storage_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load state: {e}")
            return {}

    def _save_state(self):
        """Save state to persistent storage"""
        try:
            state = {
                'date': date.today().isoformat(),
                'minutes': self._today_minutes
            }

            with open(self.storage_path, 'w') as f:
                json.dump(state, f, indent=2)

            logger.debug(f"Saved state: {self._today_minutes}min")

        except Exception as e:
            logger.error(f"Failed to save state: {e}")
