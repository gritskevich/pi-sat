"""
Morning Alarm Module

Gentle wake-up with music and volume fade-in.
Follows KISS principles - simple, focused implementation.
"""

import threading
import time
from datetime import datetime, time as dt_time, timedelta
from typing import Callable, Optional, List, Dict, Any
from enum import Enum
from modules.logging_utils import setup_logger

logger = setup_logger(__name__)


class AlarmRecurrence(Enum):
    """Alarm recurrence patterns"""
    ONCE = "once"
    DAILY = "daily"
    WEEKDAYS = "weekdays"  # Monday-Friday
    WEEKENDS = "weekends"  # Saturday-Sunday


class Alarm:
    """Single alarm configuration"""

    def __init__(
        self,
        alarm_time: str,
        query: Optional[str] = None,
        recurrence: AlarmRecurrence = AlarmRecurrence.ONCE,
        enabled: bool = True,
        alarm_id: Optional[str] = None
    ):
        """
        Create an alarm.

        Args:
            alarm_time: Wake time in HH:MM format
            query: Music query to play (None for default playlist)
            recurrence: Recurrence pattern
            enabled: Alarm is active
            alarm_id: Unique identifier
        """
        self.time = self._parse_time(alarm_time)
        self.query = query
        self.recurrence = recurrence
        self.enabled = enabled
        self.id = alarm_id or self._generate_id()
        self._last_triggered: Optional[datetime] = None

    def should_trigger(self, now: datetime) -> bool:
        """Check if alarm should trigger at given time"""
        if not self.enabled:
            return False

        # Check if already triggered today
        if self._last_triggered:
            if self._last_triggered.date() == now.date():
                return False

        # Check time match (within 1 minute window)
        now_time = now.time()
        alarm_time = self.time
        time_match = (
            alarm_time.hour == now_time.hour and
            alarm_time.minute == now_time.minute
        )

        if not time_match:
            return False

        # Check recurrence pattern
        weekday = now.weekday()  # 0=Monday, 6=Sunday

        if self.recurrence == AlarmRecurrence.ONCE:
            return True
        elif self.recurrence == AlarmRecurrence.DAILY:
            return True
        elif self.recurrence == AlarmRecurrence.WEEKDAYS:
            return weekday < 5  # Monday-Friday
        elif self.recurrence == AlarmRecurrence.WEEKENDS:
            return weekday >= 5  # Saturday-Sunday

        return False

    def mark_triggered(self):
        """Mark alarm as triggered"""
        self._last_triggered = datetime.now()
        if self.recurrence == AlarmRecurrence.ONCE:
            self.enabled = False
            logger.info(f"Alarm {self.id} disabled (one-time alarm)")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'id': self.id,
            'time': self.time.strftime('%H:%M'),
            'query': self.query,
            'recurrence': self.recurrence.value,
            'enabled': self.enabled
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'Alarm':
        """Create alarm from dictionary"""
        return Alarm(
            alarm_time=data['time'],
            query=data.get('query'),
            recurrence=AlarmRecurrence(data.get('recurrence', 'once')),
            enabled=data.get('enabled', True),
            alarm_id=data.get('id')
        )

    def _parse_time(self, time_str: str) -> dt_time:
        """Parse HH:MM time string"""
        try:
            hour, minute = map(int, time_str.split(':'))
            return dt_time(hour=hour, minute=minute)
        except Exception as e:
            logger.error(f"Invalid time format '{time_str}': {e}. Using 07:00.")
            return dt_time(hour=7, minute=0)

    def _generate_id(self) -> str:
        """Generate unique alarm ID"""
        return f"alarm_{int(time.time() * 1000)}"


class MorningAlarm:
    """
    Gentle morning alarm with music fade-in.

    Features:
    - Multiple alarms with different recurrence patterns
    - Volume fade-in (10% → 50% over 5 minutes)
    - Plays requested music or default shuffle
    - Thread-safe alarm management
    """

    def __init__(
        self,
        play_callback: Callable[[Optional[str]], bool] = None,
        get_volume_callback: Callable[[], int] = None,
        set_volume_callback: Callable[[int], None] = None,
        fade_duration: int = 300,  # 5 minutes
        start_volume: int = 10,
        end_volume: int = 50,
        debug: bool = False
    ):
        """
        Initialize morning alarm system.

        Args:
            play_callback: Function to play music (query) -> success
            get_volume_callback: Function to get current volume (0-100)
            set_volume_callback: Function to set volume (0-100)
            fade_duration: Fade-in duration in seconds (default 300s = 5 min)
            start_volume: Starting volume for fade-in (default 10%)
            end_volume: Ending volume for fade-in (default 50%)
            debug: Enable debug logging
        """
        self._play = play_callback
        self._get_volume = get_volume_callback
        self._set_volume = set_volume_callback
        self._fade_duration = fade_duration
        self._start_volume = start_volume
        self._end_volume = end_volume

        # Alarm storage
        self._alarms: List[Alarm] = []
        self._lock = threading.Lock()

        # Monitor thread
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        self.debug = debug
        if debug:
            import logging
            logger.setLevel(logging.DEBUG)

    def add_alarm(self, alarm: Alarm) -> bool:
        """
        Add new alarm.

        Returns:
            True if alarm was added successfully
        """
        with self._lock:
            # Check for duplicate time (same time, same recurrence)
            for existing in self._alarms:
                if (existing.time == alarm.time and
                    existing.recurrence == alarm.recurrence and
                    existing.enabled):
                    logger.warning(
                        f"Alarm already exists at {alarm.time.strftime('%H:%M')} "
                        f"({alarm.recurrence.value})"
                    )
                    return False

            self._alarms.append(alarm)
            logger.info(
                f"Added alarm: {alarm.time.strftime('%H:%M')} "
                f"({alarm.recurrence.value}), query='{alarm.query}'"
            )
            return True

    def remove_alarm(self, alarm_id: str) -> bool:
        """
        Remove alarm by ID.

        Returns:
            True if alarm was removed
        """
        with self._lock:
            for i, alarm in enumerate(self._alarms):
                if alarm.id == alarm_id:
                    removed = self._alarms.pop(i)
                    logger.info(f"Removed alarm: {removed.time.strftime('%H:%M')}")
                    return True

            logger.warning(f"Alarm not found: {alarm_id}")
            return False

    def get_alarms(self) -> List[Alarm]:
        """Get all alarms"""
        with self._lock:
            return list(self._alarms)

    def start_monitoring(self):
        """Start alarm monitoring thread"""
        if self._monitor_thread and self._monitor_thread.is_alive():
            logger.warning("Alarm monitoring already running")
            return

        self._stop_event.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="AlarmMonitor"
        )
        self._monitor_thread.start()
        logger.info("Alarm monitoring started")

    def stop_monitoring(self):
        """Stop alarm monitoring thread"""
        self._stop_event.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)
        logger.info("Alarm monitoring stopped")

    def _monitor_loop(self):
        """Alarm monitoring loop (runs in background thread)"""
        while not self._stop_event.is_set():
            try:
                self._check_alarms()
            except Exception as e:
                logger.error(f"Alarm monitor error: {e}")

            # Check every 30 seconds (alarms accurate to 1 minute)
            self._stop_event.wait(timeout=30)

    def _check_alarms(self):
        """Check if any alarms should trigger"""
        now = datetime.now()

        with self._lock:
            for alarm in self._alarms:
                if alarm.should_trigger(now):
                    logger.info(
                        f"⏰ Alarm triggered: {alarm.time.strftime('%H:%M')} "
                        f"({alarm.recurrence.value})"
                    )
                    alarm.mark_triggered()

                    # Trigger alarm in separate thread (non-blocking)
                    threading.Thread(
                        target=self._trigger_alarm,
                        args=(alarm,),
                        daemon=True,
                        name=f"AlarmTrigger-{alarm.id}"
                    ).start()

    def _trigger_alarm(self, alarm: Alarm):
        """Execute alarm (fade-in music)"""
        try:
            logger.info(f"Starting gentle wake-up: query='{alarm.query}'")

            # Save current volume
            original_volume = self._get_volume() if self._get_volume else 50

            # Set start volume
            if self._set_volume:
                self._set_volume(self._start_volume)

            # Start music playback
            if self._play:
                success = self._play(alarm.query)
                if not success:
                    logger.error("Failed to start alarm music")
                    # Restore original volume
                    if self._set_volume:
                        self._set_volume(original_volume)
                    return

            # Fade in volume
            steps = self._fade_duration
            volume_range = self._end_volume - self._start_volume

            for i in range(steps):
                if self._stop_event.is_set():
                    logger.info("Alarm fade-in cancelled")
                    break

                fade_volume = self._start_volume + int(volume_range * i / steps)
                if self._set_volume:
                    self._set_volume(fade_volume)

                if self.debug and i % 30 == 0:  # Log every 30 seconds
                    logger.debug(
                        f"Fade-in progress: {i}/{steps}s, volume: {fade_volume}%"
                    )

                time.sleep(1)

            # Ensure final volume is reached
            if self._set_volume and not self._stop_event.is_set():
                self._set_volume(self._end_volume)

            logger.info(
                f"Gentle wake-up completed: volume {self._start_volume}% → {self._end_volume}%"
            )

        except Exception as e:
            logger.error(f"Alarm trigger error: {e}")

    def __del__(self):
        """Cleanup on destruction"""
        try:
            self.stop_monitoring()
        except Exception:
            pass
