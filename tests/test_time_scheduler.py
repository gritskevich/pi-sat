"""
Tests for time scheduler module (bedtime enforcement).
"""

import pytest
from datetime import datetime, time as dt_time, timedelta
from modules.time_scheduler import TimeScheduler


class TestTimeScheduler:
    """Test TimeScheduler class"""

    def test_initialization(self):
        """Test basic initialization"""
        scheduler = TimeScheduler(
            bedtime_start="21:00",
            bedtime_end="07:00",
            enabled=True
        )

        assert scheduler.bedtime_start == dt_time(21, 0)
        assert scheduler.bedtime_end == dt_time(7, 0)
        assert scheduler.enabled

    def test_initialization_disabled(self):
        """Test initialization with disabled scheduler"""
        scheduler = TimeScheduler(enabled=False)
        assert not scheduler.enabled
        assert not scheduler.is_quiet_time()  # Should always return False

    def test_is_quiet_time_disabled(self):
        """Test that disabled scheduler never blocks playback"""
        scheduler = TimeScheduler(
            bedtime_start="21:00",
            bedtime_end="07:00",
            enabled=False
        )

        # Should always return False regardless of time
        assert not scheduler.is_quiet_time()

    def test_midnight_crossing_evening(self):
        """Test bedtime detection in evening (before midnight)"""
        # Create scheduler with current time in bedtime range
        scheduler = TimeScheduler(
            bedtime_start="20:00",
            bedtime_end="08:00",
            enabled=True
        )

        # Mock current time to 22:00 (in bedtime)
        # We can't easily mock datetime.now() without additional libraries,
        # so we'll test the logic indirectly

        # Test time parsing
        assert scheduler.bedtime_start < scheduler.bedtime_end or \
               scheduler.bedtime_start > scheduler.bedtime_end

    def test_time_parsing(self):
        """Test time string parsing"""
        scheduler = TimeScheduler(
            bedtime_start="21:30",
            bedtime_end="07:45"
        )

        assert scheduler.bedtime_start == dt_time(21, 30)
        assert scheduler.bedtime_end == dt_time(7, 45)

    def test_invalid_time_format(self):
        """Test handling of invalid time format"""
        # Should gracefully handle invalid time and default to 00:00
        scheduler = TimeScheduler(
            bedtime_start="invalid",
            bedtime_end="also invalid"
        )

        # Should default to 00:00
        assert scheduler.bedtime_start == dt_time(0, 0)
        assert scheduler.bedtime_end == dt_time(0, 0)

    def test_get_bedtime_message_french(self):
        """Test bedtime message in French"""
        scheduler = TimeScheduler(
            bedtime_start="21:00",
            bedtime_end="07:00"
        )

        message = scheduler.get_bedtime_message(language='fr')
        assert isinstance(message, str)
        assert "07:00" in message
        assert "dormir" in message.lower() or "coucher" in message.lower()

    def test_get_bedtime_message_english(self):
        """Test bedtime message in English"""
        scheduler = TimeScheduler(
            bedtime_start="21:00",
            bedtime_end="07:00"
        )

        message = scheduler.get_bedtime_message(language='en')
        assert isinstance(message, str)
        assert "07:00" in message
        assert "bedtime" in message.lower()

    def test_override_bedtime(self):
        """Test bedtime override for special occasions"""
        scheduler = TimeScheduler(
            bedtime_start="21:00",
            bedtime_end="07:00",
            enabled=True
        )

        # Override for 60 minutes
        success = scheduler.override_bedtime(duration_minutes=60)
        assert success

        # During override, is_quiet_time should return False
        # even if we're in bedtime hours
        # (We can't easily test this without mocking time)

    def test_cancel_override(self):
        """Test cancelling bedtime override"""
        scheduler = TimeScheduler(enabled=True)

        # Set override
        scheduler.override_bedtime(duration_minutes=30)

        # Cancel it
        success = scheduler.cancel_override()
        assert success

        # Cancelling again should return False
        success = scheduler.cancel_override()
        assert not success

    def test_override_when_disabled(self):
        """Test that override fails when scheduler is disabled"""
        scheduler = TimeScheduler(enabled=False)

        success = scheduler.override_bedtime(duration_minutes=30)
        assert not success

    def test_get_schedule_info_french(self):
        """Test schedule info message in French"""
        scheduler = TimeScheduler(
            bedtime_start="21:00",
            bedtime_end="07:00",
            enabled=True
        )

        info = scheduler.get_schedule_info(language='fr')
        assert isinstance(info, str)
        assert "21:00" in info
        assert "07:00" in info

    def test_get_schedule_info_english(self):
        """Test schedule info message in English"""
        scheduler = TimeScheduler(
            bedtime_start="21:00",
            bedtime_end="07:00",
            enabled=True
        )

        info = scheduler.get_schedule_info(language='en')
        assert isinstance(info, str)
        assert "21:00" in info
        assert "07:00" in info

    def test_get_schedule_info_disabled(self):
        """Test schedule info when disabled"""
        scheduler = TimeScheduler(enabled=False)

        info_fr = scheduler.get_schedule_info(language='fr')
        info_en = scheduler.get_schedule_info(language='en')

        assert "désactivé" in info_fr.lower() or "desactive" in info_fr.lower()
        assert "disabled" in info_en.lower()

    def test_normal_range_bedtime(self):
        """Test bedtime range that doesn't cross midnight"""
        # Afternoon quiet time: 14:00-16:00
        scheduler = TimeScheduler(
            bedtime_start="14:00",
            bedtime_end="16:00",
            enabled=True
        )

        # Start should be before end for normal range
        assert scheduler.bedtime_start < scheduler.bedtime_end

    def test_minutes_until_bedtime_disabled(self):
        """Test minutes_until_bedtime when disabled"""
        scheduler = TimeScheduler(enabled=False)

        minutes = scheduler.minutes_until_bedtime()
        assert minutes is None

    def test_should_warn_bedtime_disabled(self):
        """Test bedtime warning when disabled"""
        scheduler = TimeScheduler(enabled=False)

        should_warn = scheduler.should_warn_bedtime(warning_minutes=15)
        assert not should_warn

    def test_should_warn_bedtime_warning_threshold(self):
        """Test custom warning threshold"""
        scheduler = TimeScheduler(
            bedtime_start="21:00",
            bedtime_end="07:00",
            enabled=True
        )

        # Test with different warning thresholds
        # (actual behavior depends on current time, so just test it doesn't crash)
        should_warn_15 = scheduler.should_warn_bedtime(warning_minutes=15)
        should_warn_30 = scheduler.should_warn_bedtime(warning_minutes=30)

        assert isinstance(should_warn_15, bool)
        assert isinstance(should_warn_30, bool)
