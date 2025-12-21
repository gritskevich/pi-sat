"""
Activity Tracker - Daily Listening Time Limits & Usage Tracking

Tracks music listening time and enforces daily limits for kids.
Provides usage statistics and warnings before limit is reached.

Key Features:
- Track daily listening time
- Enforce daily time limits (e.g., max 2 hours per day)
- Warning before limit reached
- Reset at midnight
- Usage statistics and reports
- Persistent storage across restarts

Example Usage:
    tracker = ActivityTracker()

    # Start tracking playback
    tracker.start_tracking()

    # Check if limit reached
    if tracker.is_limit_reached():
        stop_playback()

    # Get remaining time
    minutes_left = tracker.get_remaining_minutes()
"""

import logging
from datetime import datetime, date, timedelta
from typing import Optional, Tuple, Dict
import threading
import json
import os

import config

logger = logging.getLogger(__name__)


class ActivityTracker:
    """
    Tracks daily music listening activity and enforces time limits.

    Manages daily listening time with configurable limits and warnings.
    """

    def __init__(
        self,
        enabled: bool = None,
        daily_limit_minutes: int = None,
        warning_minutes: int = None,
        storage_path: str = None,
        debug: bool = False
    ):
        """
        Initialize Activity Tracker.

        Args:
            enabled: Enable time limit enforcement (default: from config)
            daily_limit_minutes: Daily time limit in minutes (default: from config)
            warning_minutes: Warn when X minutes remain (default: from config)
            storage_path: Path to store usage data (default: ~/.pisat_usage.json)
            debug: Enable debug logging
        """
        self.enabled = enabled if enabled is not None else config.DAILY_TIME_LIMIT_ENABLED
        self.daily_limit_minutes = daily_limit_minutes or config.DAILY_TIME_LIMIT_MINUTES
        self.warning_minutes = warning_minutes or config.TIME_LIMIT_WARNING_MINUTES
        self.storage_path = storage_path or os.path.expanduser('~/.pisat_usage.json')
        self.debug = debug

        # Tracking state
        self._current_session_start: Optional[datetime] = None
        self._today_total_seconds: int = 0
        self._last_date: Optional[date] = None
        self._lock = threading.Lock()
        self._warned = False

        # Load saved data
        self._load_usage_data()

        if debug:
            logger.setLevel(logging.DEBUG)

        logger.info(
            f"Activity Tracker initialized: "
            f"enabled={self.enabled}, "
            f"limit={self.daily_limit_minutes} min/day"
        )

    def _load_usage_data(self):
        """Load usage data from persistent storage"""
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)

                # Parse saved date
                saved_date = date.fromisoformat(data.get('date', str(date.today())))

                # Only restore if from today
                if saved_date == date.today():
                    self._today_total_seconds = data.get('total_seconds', 0)
                    self._last_date = saved_date
                    logger.info(f"Loaded usage data: {self._today_total_seconds // 60} minutes used today")
                else:
                    # Old data, start fresh
                    self._today_total_seconds = 0
                    self._last_date = date.today()
                    logger.info("Starting new day, usage reset")
        except Exception as e:
            logger.warning(f"Failed to load usage data: {e}")
            self._today_total_seconds = 0
            self._last_date = date.today()

    def _save_usage_data(self):
        """Save usage data to persistent storage"""
        try:
            data = {
                'date': str(self._last_date or date.today()),
                'total_seconds': self._today_total_seconds
            }

            with open(self.storage_path, 'w') as f:
                json.dump(data, f)

            if self.debug:
                logger.debug(f"Saved usage data: {self._today_total_seconds // 60} minutes")

        except Exception as e:
            logger.error(f"Failed to save usage data: {e}")

    def start_tracking(self) -> bool:
        """
        Start tracking current session.

        Returns:
            True if tracking started, False if limit already reached
        """
        with self._lock:
            # Check if new day
            self._check_and_reset_if_new_day()

            # Check if limit reached
            if self.is_limit_reached():
                return False

            # Start new session
            self._current_session_start = datetime.now()
            logger.info("Started tracking playback session")
            return True

    def stop_tracking(self):
        """Stop tracking current session and save accumulated time"""
        with self._lock:
            if self._current_session_start is None:
                return

            # Calculate session duration
            session_duration = (datetime.now() - self._current_session_start).total_seconds()
            self._today_total_seconds += int(session_duration)

            logger.info(f"Session ended: {int(session_duration // 60)} minutes")
            logger.info(f"Total today: {self._today_total_seconds // 60} minutes")

            # Reset session
            self._current_session_start = None

            # Save data
            self._save_usage_data()

    def pause_tracking(self):
        """Pause tracking (e.g., when music is paused)"""
        self.stop_tracking()

    def resume_tracking(self):
        """Resume tracking (e.g., when music is resumed)"""
        self.start_tracking()

    def is_limit_reached(self) -> bool:
        """
        Check if daily time limit has been reached.

        Returns:
            True if limit reached or exceeded
        """
        if not self.enabled:
            return False

        with self._lock:
            # Include current session time
            total_seconds = self._get_total_seconds_today()
            limit_seconds = self.daily_limit_minutes * 60

            return total_seconds >= limit_seconds

    def get_remaining_minutes(self) -> Optional[int]:
        """
        Get remaining listening time for today.

        Returns:
            Minutes remaining, or None if limits disabled
        """
        if not self.enabled:
            return None

        with self._lock:
            total_seconds = self._get_total_seconds_today()
            limit_seconds = self.daily_limit_minutes * 60
            remaining_seconds = max(0, limit_seconds - total_seconds)

            return int(remaining_seconds // 60)

    def get_used_minutes(self) -> int:
        """
        Get total listening time used today.

        Returns:
            Minutes used today
        """
        with self._lock:
            total_seconds = self._get_total_seconds_today()
            return int(total_seconds // 60)

    def should_warn_about_limit(self) -> Tuple[bool, Optional[int]]:
        """
        Check if we should warn about approaching time limit.

        Returns:
            Tuple of (should_warn, minutes_remaining)
        """
        if not self.enabled:
            return (False, None)

        with self._lock:
            # Don't warn multiple times
            if self._warned:
                return (False, None)

            minutes_remaining = self.get_remaining_minutes()

            if minutes_remaining is None:
                return (False, None)

            if 0 < minutes_remaining <= self.warning_minutes:
                self._warned = True
                return (True, minutes_remaining)

            return (False, None)

    def get_usage_summary(self) -> str:
        """
        Get human-readable usage summary.

        Returns:
            Usage summary message
        """
        if not self.enabled:
            return "Time limits are not enabled"

        used_minutes = self.get_used_minutes()
        remaining_minutes = self.get_remaining_minutes()

        if self.is_limit_reached():
            return f"You've used all {self.daily_limit_minutes} minutes for today. Try again tomorrow!"
        else:
            return (
                f"You've listened for {used_minutes} minutes today. "
                f"{remaining_minutes} minutes remaining."
            )

    def reset_daily_limit(self):
        """Reset daily usage (for new day or manual reset)"""
        with self._lock:
            self._today_total_seconds = 0
            self._last_date = date.today()
            self._current_session_start = None
            self._warned = False
            self._save_usage_data()
            logger.info("Daily usage reset")

    def _check_and_reset_if_new_day(self):
        """Check if it's a new day and reset if needed"""
        today = date.today()

        if self._last_date != today:
            logger.info("New day detected, resetting usage")
            self._today_total_seconds = 0
            self._last_date = today
            self._warned = False
            self._save_usage_data()

    def _get_total_seconds_today(self) -> int:
        """
        Get total seconds including current session.

        Returns:
            Total seconds of playback today
        """
        total = self._today_total_seconds

        # Add current session if active
        if self._current_session_start:
            session_duration = (datetime.now() - self._current_session_start).total_seconds()
            total += int(session_duration)

        return total


def main():
    """Test Activity Tracker"""
    import logging
    import time
    logging.basicConfig(level=logging.INFO)

    print("Activity Tracker Test\n")
    print("=" * 60)

    # Test with 5-minute limit for demonstration
    tracker = ActivityTracker(
        enabled=True,
        daily_limit_minutes=5,
        warning_minutes=2,
        storage_path='/tmp/pisat_usage_test.json',
        debug=True
    )

    print("\n1. Initial state:")
    print(f"   {tracker.get_usage_summary()}")

    # Simulate 3 minutes of playback
    print("\n2. Simulating 3 minutes of playback:")
    tracker.start_tracking()
    print("   Started tracking...")
    time.sleep(3)  # Simulate 3 seconds (pretend it's 3 minutes)
    tracker._today_total_seconds = 180  # Set to 3 minutes for demo
    tracker.stop_tracking()
    print(f"   {tracker.get_usage_summary()}")

    # Check warning
    print("\n3. Checking for warning:")
    should_warn, mins = tracker.should_warn_about_limit()
    if should_warn:
        print(f"   ⚠️  Warning: {mins} minutes remaining!")

    # Add more time to reach limit
    print("\n4. Adding 2 more minutes (reaching limit):")
    tracker._today_total_seconds = 300  # 5 minutes total
    tracker._save_usage_data()
    print(f"   {tracker.get_usage_summary()}")
    print(f"   Limit reached: {tracker.is_limit_reached()}")

    # Try to start tracking after limit
    print("\n5. Trying to start tracking after limit:")
    if tracker.start_tracking():
        print("   Started tracking")
    else:
        print("   ✗ Cannot start - limit reached")

    # Reset
    print("\n6. Resetting usage:")
    tracker.reset_daily_limit()
    print(f"   {tracker.get_usage_summary()}")


if __name__ == '__main__':
    main()
