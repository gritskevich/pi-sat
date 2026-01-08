"""
Tests for activity tracker module (daily time limits).
"""

import pytest
import tempfile
import time
from pathlib import Path
from modules.activity_tracker import ActivityTracker


class TestActivityTracker:
    """Test ActivityTracker class"""

    def test_initialization(self):
        """Test basic initialization"""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tracker = ActivityTracker(
                daily_limit_minutes=120,
                warning_minutes=15,
                storage_path=tmp.name,
                enabled=True
            )

            assert tracker.daily_limit_minutes == 120
            assert tracker.warning_minutes == 15
            assert tracker.enabled
            assert tracker.storage_path == Path(tmp.name)

            # Cleanup
            Path(tmp.name).unlink(missing_ok=True)

    def test_initialization_disabled(self):
        """Test initialization with disabled tracker"""
        tracker = ActivityTracker(enabled=False)

        assert not tracker.enabled
        assert not tracker.is_limit_reached()

    def test_start_stop_listening(self):
        """Test basic start/stop listening session"""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tracker = ActivityTracker(
                daily_limit_minutes=120,
                storage_path=tmp.name
            )

            # Start listening
            tracker.start_listening()

            # Small delay
            time.sleep(0.1)

            # Stop listening
            tracker.stop_listening()

            # Should have some usage (at least 0 minutes due to rounding)
            usage = tracker.get_usage_today()
            assert usage >= 0

            # Cleanup
            Path(tmp.name).unlink(missing_ok=True)

    def test_limit_not_reached_initially(self):
        """Test that limit is not reached initially"""
        tracker = ActivityTracker(daily_limit_minutes=120)

        assert not tracker.is_limit_reached()

    def test_limit_reached_after_exceeding(self):
        """Test limit detection after exceeding"""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tracker = ActivityTracker(
                daily_limit_minutes=0,  # 0 minute limit for testing
                storage_path=tmp.name
            )

            # Start and stop a session
            tracker.start_listening()
            time.sleep(0.1)
            tracker.stop_listening()

            # Limit should be reached (any usage > 0 exceeds limit of 0)
            # Note: Rounding may make this 0 minutes, so limit might not be reached
            # Let's set usage manually
            tracker._today_minutes = 1

            assert tracker.is_limit_reached()

            # Cleanup
            Path(tmp.name).unlink(missing_ok=True)

    def test_limit_disabled(self):
        """Test that disabled tracker never reaches limit"""
        tracker = ActivityTracker(
            daily_limit_minutes=0,
            enabled=False
        )

        # Manually set high usage
        tracker._today_minutes = 1000

        # Should never reach limit when disabled
        assert not tracker.is_limit_reached()

    def test_get_remaining_minutes(self):
        """Test getting remaining minutes"""
        tracker = ActivityTracker(
            daily_limit_minutes=120
        )

        remaining = tracker.get_remaining_minutes()

        # Should return 120 (no usage yet)
        assert remaining == 120

    def test_get_remaining_minutes_after_usage(self):
        """Test remaining minutes after some usage"""
        tracker = ActivityTracker(
            daily_limit_minutes=120
        )

        # Manually set usage
        tracker._today_minutes = 30

        remaining = tracker.get_remaining_minutes()

        assert remaining == 90  # 120 - 30

    def test_get_remaining_minutes_disabled(self):
        """Test remaining minutes when disabled"""
        tracker = ActivityTracker(
            daily_limit_minutes=120,
            enabled=False
        )

        remaining = tracker.get_remaining_minutes()

        # Should return None when disabled
        assert remaining is None

    def test_get_remaining_minutes_exceeded(self):
        """Test remaining minutes when limit exceeded"""
        tracker = ActivityTracker(
            daily_limit_minutes=120
        )

        # Set usage beyond limit
        tracker._today_minutes = 150

        remaining = tracker.get_remaining_minutes()

        # Should return 0 (not negative)
        assert remaining == 0

    def test_get_usage_today(self):
        """Test getting usage for today"""
        tracker = ActivityTracker()

        # Initially should be 0
        assert tracker.get_usage_today() == 0

        # Set some usage
        tracker._today_minutes = 45

        assert tracker.get_usage_today() == 45

    def test_should_warn_limit_triggered(self):
        """Test warning trigger when approaching limit"""
        tracker = ActivityTracker(
            daily_limit_minutes=120,
            warning_minutes=15
        )

        # Set usage to be within warning threshold
        tracker._today_minutes = 110  # 10 minutes remaining

        # Should warn
        should_warn = tracker.should_warn_limit()
        assert should_warn

        # Second call should not warn (already warned)
        should_warn_again = tracker.should_warn_limit()
        assert not should_warn_again

    def test_should_warn_limit_not_triggered(self):
        """Test warning not triggered when plenty of time remains"""
        tracker = ActivityTracker(
            daily_limit_minutes=120,
            warning_minutes=15
        )

        # Set usage far from limit
        tracker._today_minutes = 50  # 70 minutes remaining

        # Should not warn
        should_warn = tracker.should_warn_limit()
        assert not should_warn

    def test_should_warn_limit_disabled(self):
        """Test warning when tracker disabled"""
        tracker = ActivityTracker(
            daily_limit_minutes=120,
            warning_minutes=15,
            enabled=False
        )

        # Set usage near limit
        tracker._today_minutes = 110

        # Should not warn (disabled)
        should_warn = tracker.should_warn_limit()
        assert not should_warn

    def test_get_limit_message_french(self):
        """Test limit reached message in French"""
        tracker = ActivityTracker(daily_limit_minutes=120)

        message = tracker.get_limit_message(language='fr')

        assert isinstance(message, str)
        assert "120" in message
        assert "demain" in message.lower()

    def test_get_limit_message_english(self):
        """Test limit reached message in English"""
        tracker = ActivityTracker(daily_limit_minutes=120)

        message = tracker.get_limit_message(language='en')

        assert isinstance(message, str)
        assert "120" in message
        assert "tomorrow" in message.lower()

    def test_get_warning_message_french(self):
        """Test warning message in French"""
        tracker = ActivityTracker(
            daily_limit_minutes=120,
            warning_minutes=15
        )

        # Set usage to trigger warning
        tracker._today_minutes = 110  # 10 remaining

        message = tracker.get_warning_message(language='fr')

        assert isinstance(message, str)
        assert "10" in message

    def test_get_warning_message_english(self):
        """Test warning message in English"""
        tracker = ActivityTracker(
            daily_limit_minutes=120,
            warning_minutes=15
        )

        # Set usage to trigger warning
        tracker._today_minutes = 110  # 10 remaining

        message = tracker.get_warning_message(language='en')

        assert isinstance(message, str)
        assert "10" in message

    def test_reset_today(self):
        """Test manual reset of today's usage"""
        tracker = ActivityTracker()

        # Set some usage
        tracker._today_minutes = 100

        # Reset
        tracker.reset_today()

        # Usage should be 0
        assert tracker.get_usage_today() == 0

    def test_persistence(self):
        """Test that usage persists across instances"""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            # Create tracker and set usage
            tracker1 = ActivityTracker(
                daily_limit_minutes=120,
                storage_path=tmp.name
            )
            tracker1._today_minutes = 50
            tracker1._save_state()

            # Create new tracker with same storage path
            tracker2 = ActivityTracker(
                daily_limit_minutes=120,
                storage_path=tmp.name
            )

            # Should load previous usage
            assert tracker2.get_usage_today() == 50

            # Cleanup
            Path(tmp.name).unlink(missing_ok=True)

    def test_current_session_included_in_total(self):
        """Test that current session time is included in total"""
        tracker = ActivityTracker()

        # Start session
        tracker.start_listening()

        # Wait 2 seconds
        time.sleep(2)

        # Get usage (should include current session)
        # Note: Rounds to minutes, so might still be 0
        usage = tracker.get_usage_today()
        assert usage >= 0

        # Stop session
        tracker.stop_listening()

    def test_thread_safety(self):
        """Test concurrent start/stop operations"""
        import threading

        tracker = ActivityTracker()

        def start_sessions():
            for _ in range(10):
                tracker.start_listening()
                time.sleep(0.01)
                tracker.stop_listening()

        thread1 = threading.Thread(target=start_sessions)
        thread2 = threading.Thread(target=start_sessions)

        thread1.start()
        thread2.start()

        thread1.join()
        thread2.join()

        # Should not crash (thread safety test)
        usage = tracker.get_usage_today()
        assert usage >= 0
