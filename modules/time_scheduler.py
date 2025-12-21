"""
Time Scheduler - Bedtime & Quiet Hours Enforcement

Manages scheduled quiet times for kid-friendly bedtime enforcement.
Prevents music playback during configured bedtime hours.

Key Features:
- Configurable bedtime/quiet hours (e.g., 9 PM - 7 AM)
- Warning notifications before quiet time starts
- Automatic music stop at bedtime
- Query current schedule ("What's my bedtime?")
- Temporary override for special occasions

Example Usage:
    scheduler = TimeScheduler()

    # Check if playback allowed
    if scheduler.is_playback_allowed():
        play_music()

    # Get warning before bedtime
    minutes_until = scheduler.minutes_until_quiet_time()
    if minutes_until and minutes_until <= 10:
        warn_about_bedtime(minutes_until)
"""

import logging
from datetime import datetime, time, timedelta
from typing import Optional, Tuple
import threading

import config

logger = logging.getLogger(__name__)


class TimeScheduler:
    """
    Manages time-based restrictions for kid-friendly playback control.

    Handles bedtime/quiet hours with configurable schedules and warnings.
    """

    def __init__(
        self,
        enabled: bool = None,
        start_time: str = None,
        end_time: str = None,
        warning_minutes: int = None,
        debug: bool = False
    ):
        """
        Initialize Time Scheduler.

        Args:
            enabled: Enable bedtime enforcement (default: from config)
            start_time: Bedtime start in HH:MM format (default: from config)
            end_time: Bedtime end in HH:MM format (default: from config)
            warning_minutes: Minutes before bedtime to warn (default: from config)
            debug: Enable debug logging
        """
        self.enabled = enabled if enabled is not None else config.BEDTIME_ENABLED
        self.warning_minutes = warning_minutes or config.BEDTIME_WARNING_MINUTES
        self.debug = debug

        # Parse time strings
        self.start_time = self._parse_time(start_time or config.BEDTIME_START)
        self.end_time = self._parse_time(end_time or config.BEDTIME_END)

        # Override state (for special occasions)
        self._override_until = None
        self._override_lock = threading.Lock()

        if debug:
            logger.setLevel(logging.DEBUG)

        logger.info(
            f"Time Scheduler initialized: "
            f"enabled={self.enabled}, "
            f"bedtime={self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')}"
        )

    def _parse_time(self, time_str: str) -> time:
        """
        Parse time string in HH:MM format.

        Args:
            time_str: Time in HH:MM format (24-hour)

        Returns:
            datetime.time object
        """
        try:
            hour, minute = map(int, time_str.split(':'))
            return time(hour=hour, minute=minute)
        except Exception as e:
            logger.error(f"Failed to parse time '{time_str}': {e}")
            # Default to 9 PM
            return time(hour=21, minute=0)

    def is_quiet_time(self, check_time: Optional[datetime] = None) -> bool:
        """
        Check if current time is during quiet hours (bedtime).

        Args:
            check_time: Time to check (default: now)

        Returns:
            True if in quiet hours
        """
        if not self.enabled:
            return False

        # Check for active override
        with self._override_lock:
            if self._override_until:
                if datetime.now() < self._override_until:
                    logger.debug("Bedtime override active")
                    return False
                else:
                    # Override expired
                    self._override_until = None

        now = check_time or datetime.now()
        current_time = now.time()

        # Handle overnight bedtime (e.g., 9 PM - 7 AM)
        if self.start_time > self.end_time:
            # Bedtime spans midnight
            is_quiet = current_time >= self.start_time or current_time < self.end_time
        else:
            # Same-day bedtime (unusual, but supported)
            is_quiet = self.start_time <= current_time < self.end_time

        if self.debug and is_quiet:
            logger.debug(f"Quiet time active: {current_time.strftime('%H:%M')}")

        return is_quiet

    def is_playback_allowed(self) -> Tuple[bool, Optional[str]]:
        """
        Check if music playback is currently allowed.

        Returns:
            Tuple of (allowed, reason_if_not_allowed)
        """
        if self.is_quiet_time():
            start_str = self.start_time.strftime('%H:%M')
            end_str = self.end_time.strftime('%H:%M')
            reason = f"It's bedtime. Music is not allowed between {start_str} and {end_str}"
            return (False, reason)

        return (True, None)

    def minutes_until_quiet_time(self) -> Optional[int]:
        """
        Calculate minutes until quiet time starts.

        Returns:
            Minutes until bedtime, or None if already in quiet time or disabled
        """
        if not self.enabled:
            return None

        if self.is_quiet_time():
            return None

        now = datetime.now()

        # Calculate next bedtime occurrence
        bedtime_today = datetime.combine(now.date(), self.start_time)

        # If bedtime already passed today, it's tomorrow
        if bedtime_today <= now:
            bedtime_today += timedelta(days=1)

        delta = bedtime_today - now
        minutes = int(delta.total_seconds() / 60)

        return minutes

    def should_warn_about_bedtime(self) -> Tuple[bool, Optional[int]]:
        """
        Check if we should warn about approaching bedtime.

        Returns:
            Tuple of (should_warn, minutes_remaining)
        """
        minutes_until = self.minutes_until_quiet_time()

        if minutes_until is None:
            return (False, None)

        if 0 < minutes_until <= self.warning_minutes:
            return (True, minutes_until)

        return (False, None)

    def get_schedule_info(self) -> str:
        """
        Get human-readable schedule information.

        Returns:
            Description of current bedtime schedule
        """
        if not self.enabled:
            return "Bedtime is not enabled"

        start_str = self.start_time.strftime('%I:%M %p')
        end_str = self.end_time.strftime('%I:%M %p')

        if self.is_quiet_time():
            return f"It's bedtime now. Music is allowed from {end_str} to {start_str}"
        else:
            minutes_until = self.minutes_until_quiet_time()
            if minutes_until:
                hours = minutes_until // 60
                mins = minutes_until % 60

                if hours > 0:
                    time_str = f"{hours} hour{'s' if hours > 1 else ''} and {mins} minute{'s' if mins != 1 else ''}"
                else:
                    time_str = f"{mins} minute{'s' if mins != 1 else ''}"

                return f"Bedtime is at {start_str}. That's in {time_str}"
            else:
                return f"Bedtime is at {start_str}"

    def set_override(self, duration_minutes: int) -> str:
        """
        Temporarily override bedtime restrictions.

        Args:
            duration_minutes: How long to override (minutes)

        Returns:
            Confirmation message
        """
        with self._override_lock:
            self._override_until = datetime.now() + timedelta(minutes=duration_minutes)
            logger.info(f"Bedtime override set for {duration_minutes} minutes")
            return f"Bedtime override set for {duration_minutes} minutes"

    def clear_override(self) -> str:
        """
        Clear bedtime override.

        Returns:
            Confirmation message
        """
        with self._override_lock:
            self._override_until = None
            logger.info("Bedtime override cleared")
            return "Bedtime restrictions restored"

    def update_schedule(self, start_time: Optional[str] = None, end_time: Optional[str] = None) -> str:
        """
        Update bedtime schedule.

        Args:
            start_time: New bedtime start (HH:MM format)
            end_time: New bedtime end (HH:MM format)

        Returns:
            Confirmation message
        """
        if start_time:
            self.start_time = self._parse_time(start_time)

        if end_time:
            self.end_time = self._parse_time(end_time)

        start_str = self.start_time.strftime('%I:%M %p')
        end_str = self.end_time.strftime('%I:%M %p')

        logger.info(f"Bedtime schedule updated: {start_str} - {end_str}")
        return f"Bedtime updated: {start_str} to {end_str}"


def main():
    """Test Time Scheduler"""
    import logging
    logging.basicConfig(level=logging.INFO)

    print("Time Scheduler Test\n")
    print("=" * 60)

    # Test with default config
    scheduler = TimeScheduler(debug=True)

    print(f"\n1. Bedtime enabled: {scheduler.enabled}")
    print(f"   Schedule: {scheduler.start_time.strftime('%H:%M')} - {scheduler.end_time.strftime('%H:%M')}")

    # Check current status
    print(f"\n2. Current status:")
    print(f"   Is quiet time: {scheduler.is_quiet_time()}")
    allowed, reason = scheduler.is_playback_allowed()
    print(f"   Playback allowed: {allowed}")
    if reason:
        print(f"   Reason: {reason}")

    # Check time until bedtime
    print(f"\n3. Time until bedtime:")
    minutes = scheduler.minutes_until_quiet_time()
    if minutes:
        print(f"   {minutes} minutes")
    else:
        print(f"   Already in quiet time or disabled")

    # Check warning
    print(f"\n4. Bedtime warning:")
    should_warn, mins = scheduler.should_warn_about_bedtime()
    if should_warn:
        print(f"   ⚠️  Warning: {mins} minutes until bedtime")
    else:
        print(f"   No warning needed")

    # Get schedule info
    print(f"\n5. Schedule info:")
    print(f"   {scheduler.get_schedule_info()}")

    # Test override
    print(f"\n6. Testing override:")
    msg = scheduler.set_override(30)
    print(f"   {msg}")
    print(f"   Is quiet time (with override): {scheduler.is_quiet_time()}")
    scheduler.clear_override()
    print(f"   Override cleared")

    # Test schedule update
    print(f"\n7. Testing schedule update:")
    msg = scheduler.update_schedule(start_time="22:00", end_time="08:00")
    print(f"   {msg}")


if __name__ == '__main__':
    main()
