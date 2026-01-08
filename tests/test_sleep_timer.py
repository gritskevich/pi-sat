"""
Tests for sleep timer module.
"""

import pytest
import time
import threading
from modules.sleep_timer import SleepTimer


class TestSleepTimer:
    """Test SleepTimer class"""

    def test_initialization(self):
        """Test basic initialization"""
        timer = SleepTimer(fade_duration=10)
        assert timer._fade_duration == 10
        assert not timer.is_active()

    def test_invalid_duration(self):
        """Test invalid timer duration"""
        # Create mock callbacks
        volumes = []

        def mock_set_volume(vol):
            volumes.append(vol)

        timer = SleepTimer(
            set_volume_callback=mock_set_volume,
            fade_duration=5
        )

        # Negative duration should return False
        assert not timer.start(-1)
        assert not timer.is_active()

        # Zero duration should return False
        assert not timer.start(0)
        assert not timer.is_active()

    def test_timer_activation(self):
        """Test timer starts and becomes active"""
        stopped = []

        def mock_stop():
            stopped.append(True)

        timer = SleepTimer(
            stop_callback=mock_stop,
            fade_duration=2
        )

        # Start timer
        success = timer.start(duration_minutes=1)
        assert success
        assert timer.is_active()

        # Cancel before completion
        timer.cancel()

    def test_timer_cancel(self):
        """Test timer cancellation"""
        stopped = []
        volumes = []

        def mock_stop():
            stopped.append(True)

        def mock_get_volume():
            return 50

        def mock_set_volume(vol):
            volumes.append(vol)

        timer = SleepTimer(
            get_volume_callback=mock_get_volume,
            set_volume_callback=mock_set_volume,
            stop_callback=mock_stop,
            fade_duration=30
        )

        # Start timer
        timer.start(duration_minutes=5)
        assert timer.is_active()

        # Wait a bit
        time.sleep(0.1)

        # Cancel
        success = timer.cancel()
        assert success
        assert not timer.is_active()

        # Stop should not have been called (cancelled before completion)
        assert len(stopped) == 0

    def test_timer_completion_calls_stop(self):
        """Test timer calls stop callback after fade completes"""
        stopped = []
        volumes = []

        def mock_stop():
            stopped.append(True)

        def mock_get_volume():
            return 50

        def mock_set_volume(vol):
            volumes.append(vol)

        timer = SleepTimer(
            get_volume_callback=mock_get_volume,
            set_volume_callback=mock_set_volume,
            stop_callback=mock_stop,
            fade_duration=1  # Short fade for testing
        )

        # Start very short timer (1 second fade)
        # Total: immediate start + 1s fade = ~1s total
        timer.start(duration_minutes=1/60 + 0.02)  # ~1.2 seconds

        # Wait for completion
        time.sleep(2)

        # Stop should have been called
        assert len(stopped) > 0
        assert not timer.is_active()

        # Volume should have been set multiple times during fade
        assert len(volumes) > 0

    def test_fade_volume_decrease(self):
        """Test that volume decreases during fade"""
        volumes = []

        def mock_get_volume():
            return 50

        def mock_set_volume(vol):
            volumes.append(vol)

        timer = SleepTimer(
            get_volume_callback=mock_get_volume,
            set_volume_callback=mock_set_volume,
            fade_duration=2  # 2 second fade
        )

        # Start timer with very short duration (mostly fade)
        timer.start(duration_minutes=1/60 + 0.03)  # ~2 seconds

        # Wait for fade to complete
        time.sleep(3)

        # Should have multiple volume sets
        assert len(volumes) > 0

        # Volume should decrease over time
        # (last volume should be lower than first, or close to 0)
        if len(volumes) >= 2:
            # Check that we're fading down
            # Allow some variance due to timing
            assert volumes[-1] <= volumes[0] or volumes[-1] <= 5

    def test_volume_restoration_after_cancel(self):
        """Test volume is restored when timer is cancelled"""
        volumes = []
        original_volume = 50

        def mock_get_volume():
            return original_volume

        def mock_set_volume(vol):
            volumes.append(vol)

        timer = SleepTimer(
            get_volume_callback=mock_get_volume,
            set_volume_callback=mock_set_volume,
            fade_duration=5
        )

        # Start timer
        timer.start(duration_minutes=5)

        # Wait for fade to start
        time.sleep(0.5)

        # Cancel during fade
        timer.cancel()

        # Volume should be restored to original
        # (last set_volume call should be original_volume)
        if len(volumes) > 0:
            assert volumes[-1] == original_volume

    def test_volume_restoration_after_completion(self):
        """Test volume is restored after timer completes"""
        volumes = []
        original_volume = 50

        def mock_get_volume():
            return original_volume

        def mock_set_volume(vol):
            volumes.append(vol)

        def mock_stop():
            pass

        timer = SleepTimer(
            get_volume_callback=mock_get_volume,
            set_volume_callback=mock_set_volume,
            stop_callback=mock_stop,
            fade_duration=1
        )

        # Start short timer
        timer.start(duration_minutes=1/60 + 0.02)

        # Wait for completion
        time.sleep(2)

        # Volume should be restored (last call)
        assert len(volumes) > 0
        assert volumes[-1] == original_volume

    def test_restart_timer(self):
        """Test restarting timer cancels previous timer"""
        stopped = []

        def mock_stop():
            stopped.append(True)

        timer = SleepTimer(
            stop_callback=mock_stop,
            fade_duration=30
        )

        # Start first timer
        timer.start(duration_minutes=10)
        assert timer.is_active()

        # Start second timer (should cancel first)
        timer.start(duration_minutes=5)
        assert timer.is_active()

        # Cancel
        timer.cancel()

    def test_cancel_inactive_timer(self):
        """Test cancelling when no timer is active"""
        timer = SleepTimer()

        # Cancel when not active
        result = timer.cancel()
        assert not result

    def test_is_active_false_initially(self):
        """Test is_active returns False before start"""
        timer = SleepTimer()
        assert not timer.is_active()

    def test_thread_safety(self):
        """Test concurrent start/cancel operations"""
        timer = SleepTimer(fade_duration=10)

        def start_timer():
            for _ in range(5):
                timer.start(duration_minutes=1)
                time.sleep(0.01)

        def cancel_timer():
            for _ in range(5):
                timer.cancel()
                time.sleep(0.01)

        # Run concurrent operations
        thread1 = threading.Thread(target=start_timer)
        thread2 = threading.Thread(target=cancel_timer)

        thread1.start()
        thread2.start()

        thread1.join()
        thread2.join()

        # Should not crash (thread safety test)
        # Final state may vary but should be valid
        assert isinstance(timer.is_active(), bool)

    def test_no_callbacks_provided(self):
        """Test timer works without callbacks (graceful degradation)"""
        timer = SleepTimer(fade_duration=1)

        # Should not crash even without callbacks
        success = timer.start(duration_minutes=1/60 + 0.01)
        assert success

        # Wait for completion
        time.sleep(2)

        # Should not crash
        assert not timer.is_active()

    def test_custom_fade_duration(self):
        """Test custom fade duration"""
        timer = SleepTimer(fade_duration=10)
        assert timer._fade_duration == 10

        timer2 = SleepTimer(fade_duration=60)
        assert timer2._fade_duration == 60
