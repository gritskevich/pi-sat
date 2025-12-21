"""
Morning Alarm - Wake-up with Music & Gentle Volume Increase

Manages morning alarms with gentle wake-up feature.
Gradually increases volume over configured duration for pleasant wake-up.

Key Features:
- Set alarms with wake-up time and music
- Gentle volume fade-in (e.g., 10% → 50% over 5 minutes)
- Multiple alarms support
- Recurring alarms (daily, weekdays, weekends)
- Cancel/snooze alarms
- Voice commands: "Wake me up at 7 AM with Frozen"

Example Usage:
    alarm = MorningAlarm(mpd_controller)

    # Set alarm
    alarm.set_alarm(
        wake_time="07:00",
        music_query="Frozen",
        gentle_wakeup=True
    )

    # Check and trigger alarms (called by main loop)
    if alarm.check_and_trigger():
        print("Alarm triggered!")
"""

import logging
from datetime import datetime, time, timedelta
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass
import threading
import time as time_module

import config

logger = logging.getLogger(__name__)


@dataclass
class Alarm:
    """Alarm configuration"""
    id: int
    wake_time: time
    music_query: Optional[str]
    gentle_wakeup: bool
    enabled: bool
    recurring: str  # 'once', 'daily', 'weekdays', 'weekends'
    next_trigger: datetime

    def __repr__(self):
        time_str = self.wake_time.strftime('%I:%M %p')
        music_str = f" with {self.music_query}" if self.music_query else ""
        return f"Alarm({time_str}{music_str}, {self.recurring})"


class MorningAlarm:
    """
    Morning alarm system with gentle wake-up support.

    Manages multiple alarms with gradual volume increase for pleasant waking.
    """

    def __init__(
        self,
        mpd_controller=None,
        gentle_wakeup_duration: int = None,
        start_volume: int = None,
        end_volume: int = None,
        debug: bool = False
    ):
        """
        Initialize Morning Alarm.

        Args:
            mpd_controller: MPD controller instance for playback
            gentle_wakeup_duration: Seconds for volume fade-in (default: from config)
            start_volume: Starting volume percentage (default: from config)
            end_volume: Ending volume percentage (default: from config)
            debug: Enable debug logging
        """
        self.mpd_controller = mpd_controller
        self.gentle_wakeup_duration = gentle_wakeup_duration or config.ALARM_GENTLE_WAKEUP_DURATION
        self.start_volume = start_volume or config.ALARM_START_VOLUME
        self.end_volume = end_volume or config.ALARM_END_VOLUME
        self.debug = debug

        # Alarm storage
        self._alarms: List[Alarm] = []
        self._next_alarm_id = 1
        self._alarms_lock = threading.Lock()

        # Active alarm state
        self._active_alarm_thread = None
        self._active_alarm_cancel = threading.Event()

        if debug:
            logger.setLevel(logging.DEBUG)

        logger.info(
            f"Morning Alarm initialized: "
            f"gentle_wakeup={self.gentle_wakeup_duration}s, "
            f"volume={self.start_volume}→{self.end_volume}%"
        )

    def set_alarm(
        self,
        wake_time: str,
        music_query: Optional[str] = None,
        gentle_wakeup: bool = True,
        recurring: str = 'once'
    ) -> Tuple[bool, str]:
        """
        Set a new alarm.

        Args:
            wake_time: Wake time in HH:MM format (24-hour)
            music_query: Music to play (None for favorites or current playlist)
            gentle_wakeup: Enable gentle volume fade-in
            recurring: 'once', 'daily', 'weekdays', 'weekends'

        Returns:
            Tuple of (success, message)
        """
        try:
            # Parse wake time
            alarm_time = self._parse_time(wake_time)

            # Calculate next trigger
            next_trigger = self._calculate_next_trigger(alarm_time, recurring)

            with self._alarms_lock:
                # Create new alarm
                alarm = Alarm(
                    id=self._next_alarm_id,
                    wake_time=alarm_time,
                    music_query=music_query,
                    gentle_wakeup=gentle_wakeup,
                    enabled=True,
                    recurring=recurring,
                    next_trigger=next_trigger
                )

                self._alarms.append(alarm)
                self._next_alarm_id += 1

            time_str = alarm_time.strftime('%I:%M %p')
            music_str = f" with {music_query}" if music_query else ""

            logger.info(f"Alarm set: {time_str}{music_str} ({recurring})")
            return (True, f"Alarm set for {time_str}{music_str}")

        except Exception as e:
            logger.error(f"Failed to set alarm: {e}")
            return (False, f"I couldn't set the alarm: {e}")

    def cancel_alarm(self, alarm_id: Optional[int] = None) -> Tuple[bool, str]:
        """
        Cancel alarm(s).

        Args:
            alarm_id: Specific alarm ID to cancel (None = cancel all)

        Returns:
            Tuple of (success, message)
        """
        with self._alarms_lock:
            if alarm_id is None:
                # Cancel all alarms
                count = len(self._alarms)
                self._alarms.clear()
                return (True, f"Cancelled {count} alarm{'s' if count != 1 else ''}")
            else:
                # Cancel specific alarm
                self._alarms = [a for a in self._alarms if a.id != alarm_id]
                return (True, f"Alarm cancelled")

    def get_alarms(self) -> List[Alarm]:
        """
        Get list of all alarms.

        Returns:
            List of Alarm objects
        """
        with self._alarms_lock:
            return self._alarms.copy()

    def get_next_alarm(self) -> Optional[Alarm]:
        """
        Get next alarm that will trigger.

        Returns:
            Next Alarm object or None
        """
        with self._alarms_lock:
            if not self._alarms:
                return None

            # Find alarm with earliest next_trigger
            enabled_alarms = [a for a in self._alarms if a.enabled]
            if not enabled_alarms:
                return None

            return min(enabled_alarms, key=lambda a: a.next_trigger)

    def check_and_trigger(self) -> bool:
        """
        Check if any alarms should trigger and start them.

        Should be called regularly by main loop (e.g., every minute).

        Returns:
            True if an alarm was triggered
        """
        now = datetime.now()

        with self._alarms_lock:
            for alarm in self._alarms:
                if not alarm.enabled:
                    continue

                # Check if alarm should trigger
                if now >= alarm.next_trigger:
                    logger.info(f"Triggering alarm: {alarm}")

                    # Trigger alarm in background thread
                    self._trigger_alarm(alarm)

                    # Update next trigger for recurring alarms
                    if alarm.recurring == 'once':
                        alarm.enabled = False
                    else:
                        alarm.next_trigger = self._calculate_next_trigger(
                            alarm.wake_time,
                            alarm.recurring
                        )

                    return True

        return False

    def _trigger_alarm(self, alarm: Alarm):
        """
        Trigger alarm playback.

        Args:
            alarm: Alarm to trigger
        """
        # Cancel any active alarm
        if self._active_alarm_thread and self._active_alarm_thread.is_alive():
            self._active_alarm_cancel.set()
            self._active_alarm_thread.join(timeout=1)

        self._active_alarm_cancel.clear()

        def alarm_worker():
            """Worker thread for alarm playback"""
            try:
                if not self.mpd_controller:
                    logger.error("No MPD controller available")
                    return

                # Start playing music
                if alarm.music_query:
                    success, msg, _confidence = self.mpd_controller.play(alarm.music_query)
                    if not success:
                        logger.warning(f"Alarm music not found, playing favorites")
                        self.mpd_controller.play_favorites()
                else:
                    # Play favorites or resume current
                    self.mpd_controller.play()

                # Gentle wake-up: gradual volume increase
                if alarm.gentle_wakeup:
                    logger.info(
                        f"Starting gentle wake-up: "
                        f"{self.start_volume}% → {self.end_volume}% "
                        f"over {self.gentle_wakeup_duration}s"
                    )

                    steps = 30  # Number of volume adjustment steps
                    sleep_time = self.gentle_wakeup_duration / steps
                    volume_step = (self.end_volume - self.start_volume) / steps

                    # Set initial volume
                    with self.mpd_controller._ensure_connection():
                        self.mpd_controller.client.setvol(self.start_volume)

                    # Gradually increase volume
                    for i in range(steps):
                        if self._active_alarm_cancel.is_set():
                            logger.info("Alarm cancelled during wake-up")
                            return

                        current_volume = int(self.start_volume + (volume_step * i))
                        with self.mpd_controller._ensure_connection():
                            self.mpd_controller.client.setvol(current_volume)

                        time_module.sleep(sleep_time)

                    # Set final volume
                    with self.mpd_controller._ensure_connection():
                        self.mpd_controller.client.setvol(self.end_volume)

                else:
                    # No gentle wake-up, set volume immediately
                    with self.mpd_controller._ensure_connection():
                        self.mpd_controller.client.setvol(self.end_volume)

                logger.info("Alarm wake-up complete")

            except Exception as e:
                logger.error(f"Alarm playback error: {e}")

        # Start alarm thread
        self._active_alarm_thread = threading.Thread(
            target=alarm_worker,
            daemon=True
        )
        self._active_alarm_thread.start()

    def _parse_time(self, time_str: str) -> time:
        """
        Parse time string in HH:MM format.

        Args:
            time_str: Time in HH:MM format (24-hour)

        Returns:
            datetime.time object
        """
        hour, minute = map(int, time_str.split(':'))
        return time(hour=hour, minute=minute)

    def _calculate_next_trigger(self, alarm_time: time, recurring: str) -> datetime:
        """
        Calculate next trigger datetime for alarm.

        Args:
            alarm_time: Time of day for alarm
            recurring: Recurrence pattern

        Returns:
            Next datetime when alarm should trigger
        """
        now = datetime.now()
        today = now.date()

        # Start with today at alarm time
        next_trigger = datetime.combine(today, alarm_time)

        # If alarm time already passed today, start from tomorrow
        if next_trigger <= now:
            next_trigger += timedelta(days=1)

        # Handle recurring patterns
        if recurring == 'weekdays':
            # Find next weekday (Monday=0, Sunday=6)
            while next_trigger.weekday() >= 5:  # Saturday=5, Sunday=6
                next_trigger += timedelta(days=1)

        elif recurring == 'weekends':
            # Find next weekend day
            while next_trigger.weekday() < 5:  # Mon-Fri
                next_trigger += timedelta(days=1)

        return next_trigger


def main():
    """Test Morning Alarm"""
    import logging
    logging.basicConfig(level=logging.INFO)

    print("Morning Alarm Test\n")
    print("=" * 60)

    # Test without MPD (dry run)
    alarm_manager = MorningAlarm(debug=True)

    # Set some test alarms
    print("\n1. Setting alarms:")

    success, msg = alarm_manager.set_alarm(
        wake_time="07:00",
        music_query="Frozen",
        recurring='daily'
    )
    print(f"   {msg}")

    success, msg = alarm_manager.set_alarm(
        wake_time="08:30",
        music_query="Beatles",
        recurring='weekdays'
    )
    print(f"   {msg}")

    # Get all alarms
    print("\n2. All alarms:")
    alarms = alarm_manager.get_alarms()
    for alarm in alarms:
        next_str = alarm.next_trigger.strftime('%Y-%m-%d %I:%M %p')
        print(f"   {alarm} → Next: {next_str}")

    # Get next alarm
    print("\n3. Next alarm:")
    next_alarm = alarm_manager.get_next_alarm()
    if next_alarm:
        time_str = next_alarm.wake_time.strftime('%I:%M %p')
        next_str = next_alarm.next_trigger.strftime('%Y-%m-%d %I:%M %p')
        print(f"   {time_str} → {next_str}")

    # Cancel all
    print("\n4. Cancelling alarms:")
    success, msg = alarm_manager.cancel_alarm()
    print(f"   {msg}")


if __name__ == '__main__':
    main()
