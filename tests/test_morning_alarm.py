"""
Tests for morning alarm module.
"""

import pytest
import time
from datetime import datetime, time as dt_time
from modules.morning_alarm import Alarm, AlarmRecurrence, MorningAlarm


class TestAlarm:
    """Test Alarm class"""

    def test_initialization_basic(self):
        """Test basic alarm initialization"""
        alarm = Alarm(
            alarm_time="07:00",
            query="Frozen",
            recurrence=AlarmRecurrence.DAILY
        )

        assert alarm.time == dt_time(7, 0)
        assert alarm.query == "Frozen"
        assert alarm.recurrence == AlarmRecurrence.DAILY
        assert alarm.enabled

    def test_initialization_once(self):
        """Test one-time alarm"""
        alarm = Alarm(
            alarm_time="08:30",
            recurrence=AlarmRecurrence.ONCE
        )

        assert alarm.recurrence == AlarmRecurrence.ONCE
        assert alarm.enabled

    def test_invalid_time_format(self):
        """Test invalid time format handling"""
        alarm = Alarm(alarm_time="invalid")

        # Should default to 07:00
        assert alarm.time == dt_time(7, 0)

    def test_to_dict(self):
        """Test serialization to dictionary"""
        alarm = Alarm(
            alarm_time="07:30",
            query="Morning Playlist",
            recurrence=AlarmRecurrence.WEEKDAYS
        )

        data = alarm.to_dict()

        assert data['time'] == "07:30"
        assert data['query'] == "Morning Playlist"
        assert data['recurrence'] == "weekdays"
        assert data['enabled'] == True
        assert 'id' in data

    def test_from_dict(self):
        """Test deserialization from dictionary"""
        data = {
            'id': 'test123',
            'time': '08:00',
            'query': 'Jazz',
            'recurrence': 'daily',
            'enabled': True
        }

        alarm = Alarm.from_dict(data)

        assert alarm.id == 'test123'
        assert alarm.time == dt_time(8, 0)
        assert alarm.query == 'Jazz'
        assert alarm.recurrence == AlarmRecurrence.DAILY
        assert alarm.enabled

    def test_mark_triggered_once(self):
        """Test marking one-time alarm as triggered disables it"""
        alarm = Alarm(
            alarm_time="07:00",
            recurrence=AlarmRecurrence.ONCE
        )

        assert alarm.enabled

        alarm.mark_triggered()

        assert not alarm.enabled

    def test_mark_triggered_daily(self):
        """Test marking daily alarm as triggered doesn't disable it"""
        alarm = Alarm(
            alarm_time="07:00",
            recurrence=AlarmRecurrence.DAILY
        )

        assert alarm.enabled

        alarm.mark_triggered()

        assert alarm.enabled  # Should still be enabled

    def test_unique_id_generation(self):
        """Test that each alarm gets unique ID"""
        alarm1 = Alarm(alarm_time="07:00")
        time.sleep(0.01)  # Ensure different timestamp
        alarm2 = Alarm(alarm_time="07:00")

        assert alarm1.id != alarm2.id


class TestMorningAlarm:
    """Test MorningAlarm class"""

    def test_initialization(self):
        """Test basic initialization"""
        played = []

        def mock_play(query):
            played.append(query)
            return True

        alarm_system = MorningAlarm(
            play_callback=mock_play,
            fade_duration=10,
            start_volume=10,
            end_volume=50
        )

        assert alarm_system._fade_duration == 10
        assert alarm_system._start_volume == 10
        assert alarm_system._end_volume == 50

    def test_add_alarm(self):
        """Test adding alarm"""
        alarm_system = MorningAlarm()

        alarm = Alarm(
            alarm_time="07:00",
            query="Morning Music",
            recurrence=AlarmRecurrence.DAILY
        )

        success = alarm_system.add_alarm(alarm)
        assert success

        alarms = alarm_system.get_alarms()
        assert len(alarms) == 1
        assert alarms[0].time == dt_time(7, 0)

    def test_add_duplicate_alarm(self):
        """Test that duplicate alarms are rejected"""
        alarm_system = MorningAlarm()

        alarm1 = Alarm(
            alarm_time="07:00",
            recurrence=AlarmRecurrence.DAILY
        )

        alarm2 = Alarm(
            alarm_time="07:00",
            recurrence=AlarmRecurrence.DAILY
        )

        # First should succeed
        assert alarm_system.add_alarm(alarm1)

        # Second should fail (duplicate time + recurrence)
        assert not alarm_system.add_alarm(alarm2)

    def test_add_different_recurrence_allowed(self):
        """Test that same time with different recurrence is allowed"""
        alarm_system = MorningAlarm()

        alarm1 = Alarm(
            alarm_time="07:00",
            recurrence=AlarmRecurrence.WEEKDAYS
        )

        alarm2 = Alarm(
            alarm_time="07:00",
            recurrence=AlarmRecurrence.WEEKENDS
        )

        assert alarm_system.add_alarm(alarm1)
        assert alarm_system.add_alarm(alarm2)

        assert len(alarm_system.get_alarms()) == 2

    def test_remove_alarm(self):
        """Test removing alarm"""
        alarm_system = MorningAlarm()

        alarm = Alarm(alarm_time="07:00")
        alarm_system.add_alarm(alarm)

        assert len(alarm_system.get_alarms()) == 1

        success = alarm_system.remove_alarm(alarm.id)
        assert success

        assert len(alarm_system.get_alarms()) == 0

    def test_remove_nonexistent_alarm(self):
        """Test removing alarm that doesn't exist"""
        alarm_system = MorningAlarm()

        success = alarm_system.remove_alarm("nonexistent")
        assert not success

    def test_get_alarms_empty(self):
        """Test getting alarms when none exist"""
        alarm_system = MorningAlarm()

        alarms = alarm_system.get_alarms()
        assert alarms == []

    def test_trigger_alarm_calls_play(self):
        """Test that triggered alarm calls play callback"""
        played = []

        def mock_play(query):
            played.append(query)
            return True

        alarm_system = MorningAlarm(
            play_callback=mock_play,
            fade_duration=1  # Short fade for testing
        )

        alarm = Alarm(
            alarm_time="07:00",
            query="Test Song"
        )

        # Manually trigger alarm (bypass time check)
        alarm_system._trigger_alarm(alarm)

        # Wait for fade to start
        time.sleep(0.2)

        # Play should have been called
        assert len(played) > 0
        assert played[0] == "Test Song"

        # Stop monitoring to clean up
        alarm_system.stop_monitoring()

    def test_trigger_alarm_sets_volume(self):
        """Test that alarm sets volume during fade-in"""
        volumes = []

        def mock_play(query):
            return True

        def mock_get_volume():
            return 50

        def mock_set_volume(vol):
            volumes.append(vol)

        alarm_system = MorningAlarm(
            play_callback=mock_play,
            get_volume_callback=mock_get_volume,
            set_volume_callback=mock_set_volume,
            fade_duration=1,  # 1 second fade
            start_volume=10,
            end_volume=50
        )

        alarm = Alarm(alarm_time="07:00")

        # Trigger alarm
        alarm_system._trigger_alarm(alarm)

        # Wait for fade to complete
        time.sleep(1.5)

        # Should have set volume multiple times
        assert len(volumes) > 0

        # First volume should be start_volume
        assert volumes[0] == 10

        # Last volume should be end_volume (or close to it)
        assert volumes[-1] >= 40  # Allow some tolerance

        alarm_system.stop_monitoring()

    def test_no_callbacks_graceful(self):
        """Test that alarm works without callbacks (graceful degradation)"""
        alarm_system = MorningAlarm(
            fade_duration=1
        )

        alarm = Alarm(alarm_time="07:00")

        # Should not crash
        alarm_system._trigger_alarm(alarm)
        time.sleep(0.1)

        alarm_system.stop_monitoring()

    def test_start_stop_monitoring(self):
        """Test starting and stopping alarm monitoring"""
        alarm_system = MorningAlarm()

        # Start monitoring
        alarm_system.start_monitoring()

        # Wait a bit
        time.sleep(0.1)

        # Stop monitoring
        alarm_system.stop_monitoring()

        # Should not crash

    def test_monitoring_already_running(self):
        """Test that starting monitoring twice is handled"""
        alarm_system = MorningAlarm()

        alarm_system.start_monitoring()
        time.sleep(0.1)

        # Start again (should warn but not crash)
        alarm_system.start_monitoring()

        alarm_system.stop_monitoring()

    def test_thread_safety(self):
        """Test concurrent alarm operations"""
        alarm_system = MorningAlarm()

        def add_alarms():
            for i in range(5):
                alarm = Alarm(alarm_time=f"0{i}:00")
                alarm_system.add_alarm(alarm)

        def remove_alarms():
            alarms = alarm_system.get_alarms()
            for alarm in alarms:
                alarm_system.remove_alarm(alarm.id)

        import threading
        thread1 = threading.Thread(target=add_alarms)
        thread2 = threading.Thread(target=remove_alarms)

        thread1.start()
        thread2.start()

        thread1.join()
        thread2.join()

        # Should not crash (thread safety test)
