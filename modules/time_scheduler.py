"""
Time Scheduler Module

Enforces bedtime/quiet hours for kid-safe music listening.
Simple implementation following KISS principles.
"""

from datetime import datetime, time as dt_time
from typing import Optional, Tuple
from modules.logging_utils import setup_logger

logger = setup_logger(__name__)


class TimeScheduler:
    """
    Enforces quiet hours (bedtime) for kid-safe usage.

    Simple design:
    - Define bedtime window (e.g., 21:00-07:00)
    - Block playback during quiet hours
    - Allow override for special occasions
    """

    def __init__(
        self,
        bedtime_start: str = "21:00",
        bedtime_end: str = "07:00",
        enabled: bool = True,
        debug: bool = False
    ):
        """
        Initialize time scheduler.

        Args:
            bedtime_start: Start of quiet hours (HH:MM format)
            bedtime_end: End of quiet hours (HH:MM format)
            enabled: Enable bedtime enforcement
            debug: Enable debug logging
        """
        self.bedtime_start = self._parse_time(bedtime_start)
        self.bedtime_end = self._parse_time(bedtime_end)
        self.enabled = enabled
        self._override_until: Optional[datetime] = None

        if debug:
            import logging
            logger.setLevel(logging.DEBUG)

        logger.info(
            f"TimeScheduler initialized: "
            f"bedtime {bedtime_start}-{bedtime_end}, "
            f"enabled={enabled}"
        )

    def is_quiet_time(self) -> bool:
        """
        Check if current time is within quiet hours.

        Returns:
            True if it's bedtime (playback should be blocked)
        """
        if not self.enabled:
            return False

        # Check for active override
        if self._override_until and datetime.now() < self._override_until:
            logger.debug("Bedtime override active")
            return False

        now = datetime.now().time()

        # Handle midnight crossing (e.g., 21:00-07:00)
        if self.bedtime_start > self.bedtime_end:
            is_quiet = now >= self.bedtime_start or now < self.bedtime_end
        else:
            # Normal range (e.g., 14:00-16:00 for afternoon quiet time)
            is_quiet = self.bedtime_start <= now < self.bedtime_end

        if is_quiet:
            logger.debug(f"Quiet time active: {now} is within bedtime hours")

        return is_quiet

    def get_bedtime_message(self, language: str = 'fr') -> str:
        """Get bedtime notification message"""
        if language == 'fr':
            return f"C'est l'heure de dormir. La musique sera disponible à {self.bedtime_end.strftime('%H:%M')}."
        else:
            return f"It's bedtime. Music will be available at {self.bedtime_end.strftime('%H:%M')}."

    def minutes_until_bedtime(self) -> Optional[int]:
        """
        Calculate minutes until bedtime starts.

        Returns:
            Minutes until bedtime, or None if already in quiet hours or disabled
        """
        if not self.enabled or self.is_quiet_time():
            return None

        now = datetime.now()
        today_bedtime = datetime.combine(now.date(), self.bedtime_start)

        # If bedtime is in the past today, it's tomorrow
        if today_bedtime < now:
            from datetime import timedelta
            today_bedtime += timedelta(days=1)

        minutes = int((today_bedtime - now).total_seconds() / 60)
        return minutes if minutes > 0 else None

    def should_warn_bedtime(self, warning_minutes: int = 15) -> bool:
        """
        Check if we should warn about approaching bedtime.

        Args:
            warning_minutes: Minutes before bedtime to start warning

        Returns:
            True if bedtime is approaching and warning should be given
        """
        minutes = self.minutes_until_bedtime()
        return minutes is not None and 0 < minutes <= warning_minutes

    def override_bedtime(self, duration_minutes: int = 60) -> bool:
        """
        Temporarily override bedtime (for special occasions).

        Args:
            duration_minutes: Override duration in minutes

        Returns:
            True if override was successful
        """
        if not self.enabled:
            logger.warning("Cannot override bedtime: scheduler disabled")
            return False

        from datetime import timedelta
        self._override_until = datetime.now() + timedelta(minutes=duration_minutes)
        logger.info(f"Bedtime override activated for {duration_minutes} minutes")
        return True

    def cancel_override(self) -> bool:
        """
        Cancel bedtime override.

        Returns:
            True if override was cancelled
        """
        if self._override_until is None:
            logger.debug("No active override to cancel")
            return False

        self._override_until = None
        logger.info("Bedtime override cancelled")
        return True

    def get_schedule_info(self, language: str = 'fr') -> str:
        """Get current schedule information"""
        if not self.enabled:
            if language == 'fr':
                return "Le contrôle d'heure de coucher est désactivé."
            else:
                return "Bedtime control is disabled."

        start_str = self.bedtime_start.strftime('%H:%M')
        end_str = self.bedtime_end.strftime('%H:%M')

        if language == 'fr':
            return f"L'heure de coucher est de {start_str} à {end_str}."
        else:
            return f"Bedtime is from {start_str} to {end_str}."

    def _parse_time(self, time_str: str) -> dt_time:
        """Parse HH:MM time string"""
        try:
            hour, minute = map(int, time_str.split(':'))
            return dt_time(hour=hour, minute=minute)
        except Exception as e:
            logger.error(f"Invalid time format '{time_str}': {e}. Using 00:00.")
            return dt_time(hour=0, minute=0)
