"""Tests for the wake-word listener's stream-recreation race fix.

The wake listener relies on `EVENT_RECORDING_FINISHED` to recreate its mic
stream after the speech recorder releases the device. A polling fallback
exists in the main loop in case the event is dropped, but it must not
fire during a normal recording cycle (which can take 2–7s) or it will
attempt to grab a busy mic and emit "Device unavailable" warnings.

These tests don't require pyaudio or the openwakeword model — they
construct a listener via __new__ and exercise the event handler / state
machine directly.
"""

import logging
import time
import unittest

from modules.control_events import ControlEvent, EVENT_RECORDING_FINISHED
from modules.wake_word_listener import (
    STREAM_RECREATE_FALLBACK_SECONDS,
    WakeWordListener,
)


def _build_bare_listener():
    """Construct a listener without running __init__ (skips hardware deps)."""
    listener = WakeWordListener.__new__(WakeWordListener)
    listener.logger = logging.getLogger("test.wake_word_listener")
    listener.cooldown = 0.5
    listener.tts_cooldown_end = 0.0
    listener.running = True
    listener.stream = None
    listener._pending_stream_reopen = False
    listener._pending_stream_reopen_at = 0.0
    listener.event_bus = None
    listener._recreate_calls = 0

    def _fake_recreate():
        listener._recreate_calls += 1
        return True

    listener._recreate_stream = _fake_recreate
    return listener


class TestStreamRecreationFallbackThreshold(unittest.TestCase):
    """The polling fallback must wait long enough for recordings to finish."""

    def test_threshold_exceeds_typical_recording_duration(self):
        # Recordings observed in the field run 2–7s. Threshold must exceed that
        # by a comfortable margin so the polling fallback doesn't race the event.
        self.assertGreaterEqual(STREAM_RECREATE_FALLBACK_SECONDS, 8.0)


class TestRecordingFinishedEventHandler(unittest.TestCase):
    """The event-driven path must clear pending state and recreate the stream."""

    def test_event_handler_clears_pending_and_recreates(self):
        listener = _build_bare_listener()
        listener._pending_stream_reopen = True
        listener._pending_stream_reopen_at = time.time()

        listener._on_recording_finished(
            ControlEvent.now(EVENT_RECORDING_FINISHED, source="test")
        )

        self.assertFalse(listener._pending_stream_reopen)
        self.assertEqual(listener._pending_stream_reopen_at, 0.0)
        self.assertEqual(listener._recreate_calls, 1)

    def test_event_handler_is_noop_when_not_pending(self):
        listener = _build_bare_listener()

        listener._on_recording_finished(
            ControlEvent.now(EVENT_RECORDING_FINISHED, source="test")
        )

        self.assertEqual(listener._recreate_calls, 0)

    def test_event_handler_keeps_pending_if_recreate_fails(self):
        listener = _build_bare_listener()

        def _failing_recreate():
            listener._recreate_calls += 1
            return False

        listener._recreate_stream = _failing_recreate
        listener._pending_stream_reopen = True
        listener._pending_stream_reopen_at = time.time() - 1.0

        before = time.time()
        listener._on_recording_finished(
            ControlEvent.now(EVENT_RECORDING_FINISHED, source="test")
        )

        # On failure, pending must be re-armed with a fresh timestamp so the
        # main-loop polling fallback eventually retries.
        self.assertTrue(listener._pending_stream_reopen)
        self.assertGreaterEqual(listener._pending_stream_reopen_at, before)


class TestNoFallbackBeforeNormalRecordingCompletes(unittest.TestCase):
    """A normal recording cycle (≤7s) finishes before the polling fallback fires."""

    def test_polling_threshold_does_not_trigger_within_normal_recording_window(self):
        # Simulate the wake-detected → recording-in-progress state.
        pending_set_at = time.time()

        # Worst-case observed recording duration in the field.
        for elapsed in (1.0, 3.0, 5.0, 7.0):
            virtual_now = pending_set_at + elapsed
            window = virtual_now - pending_set_at
            self.assertLess(
                window,
                STREAM_RECREATE_FALLBACK_SECONDS,
                f"Polling fallback would fire after {window}s — earlier than the "
                f"event handler can deliver EVENT_RECORDING_FINISHED for a {elapsed}s recording.",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
