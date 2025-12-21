"""
Tests for retry utilities module.

Tests retry logic with exponential backoff and error recovery.
"""

import unittest
import time
import sys
import os

from modules.retry_utils import retry_with_backoff, retry_transient_errors
from tests.test_base import PiSatTestBase


class TestRetryUtils(PiSatTestBase):
    """Test retry utilities with various failure scenarios"""
    
    def setUp(self):
        super().setUp()
        self.call_count = 0
        self.retry_callbacks = []
    
    def test_retry_succeeds_on_second_attempt(self):
        """Test: Retry succeeds after initial failure
        
        Given: Function fails once then succeeds
        When: Called with retry decorator
        Then: Returns success after retry
        """
        @retry_with_backoff(max_retries=2, initial_delay=0.1)
        def flaky_function():
            self.call_count += 1
            if self.call_count == 1:
                raise RuntimeError("Transient error")
            return "success"
        
        result = flaky_function()
        
        self.assertEqual(result, "success")
        self.assertEqual(self.call_count, 2)
        self._add_result("retry_succeeds", True, "Retry succeeded on second attempt")
    
    def test_retry_fails_after_max_attempts(self):
        """Test: Retry fails after max attempts
        
        Given: Function always fails
        When: Called with retry decorator
        Then: Raises exception after max retries
        """
        @retry_with_backoff(max_retries=2, initial_delay=0.1)
        def always_fails():
            self.call_count += 1
            raise RuntimeError("Persistent error")
        
        with self.assertRaises(RuntimeError):
            always_fails()
        
        self.assertEqual(self.call_count, 3)  # Initial + 2 retries
        self._add_result("retry_fails_after_max", True, "Correctly failed after max retries")
    
    def test_retry_exponential_backoff(self):
        """Test: Retry uses exponential backoff
        
        Given: Function fails multiple times
        When: Called with retry decorator
        Then: Delay increases exponentially
        """
        delays = []
        
        def track_delay(attempt, exception):
            delays.append(time.time())
        
        @retry_with_backoff(
            max_retries=3,
            initial_delay=0.1,
            backoff_factor=2.0,
            on_retry=track_delay
        )
        def flaky_function():
            self.call_count += 1
            if self.call_count < 4:
                raise RuntimeError("Transient error")
            return "success"
        
        start_time = time.time()
        result = flaky_function()
        end_time = time.time()
        
        self.assertEqual(result, "success")
        self.assertEqual(self.call_count, 4)
        
        if len(delays) >= 2:
            delay1 = delays[1] - delays[0]
            delay2 = delays[2] - delays[1] if len(delays) > 2 else None
            
            self.assertGreater(delay1, 0.08)  # ~0.1s
            if delay2:
                self.assertGreater(delay2, delay1 * 1.5)  # Exponential increase
        
        self._add_result("exponential_backoff", True, "Exponential backoff working")
    
    def test_retry_respects_max_delay(self):
        """Test: Retry respects maximum delay
        
        Given: Function fails many times
        When: Called with retry decorator
        Then: Delay never exceeds max_delay
        """
        delays = []
        start_times = []
        
        def track_delay(attempt, exception):
            start_times.append(time.time())
            if len(start_times) > 1:
                delays.append(start_times[-1] - start_times[-2])
        
        @retry_with_backoff(
            max_retries=5,
            initial_delay=0.1,
            max_delay=0.3,
            backoff_factor=2.0,
            on_retry=track_delay
        )
        def flaky_function():
            self.call_count += 1
            if self.call_count < 6:
                raise RuntimeError("Transient error")
            return "success"
        
        result = flaky_function()
        
        self.assertEqual(result, "success")
        for delay in delays:
            self.assertLessEqual(delay, 0.35)  # Allow small margin
        
        self._add_result("max_delay_respected", True, "Max delay respected")
    
    def test_retry_only_on_specified_exceptions(self):
        """Test: Retry only on specified exceptions
        
        Given: Function raises non-retryable exception
        When: Called with retry decorator
        Then: Does not retry, raises immediately
        """
        @retry_with_backoff(
            max_retries=3,
            initial_delay=0.1,
            retryable_exceptions=(RuntimeError,)
        )
        def raises_value_error():
            self.call_count += 1
            raise ValueError("Not retryable")
        
        with self.assertRaises(ValueError):
            raises_value_error()
        
        self.assertEqual(self.call_count, 1)  # No retries
        self._add_result("exception_filtering", True, "Only retries specified exceptions")
    
    def test_retry_transient_errors_decorator(self):
        """Test: retry_transient_errors decorator works
        
        Given: Function raises transient error
        When: Called with retry_transient_errors decorator
        Then: Retries on transient errors
        """
        @retry_transient_errors(max_retries=2, initial_delay=0.1)
        def flaky_function():
            self.call_count += 1
            if self.call_count == 1:
                raise ConnectionError("Connection lost")
            return "success"
        
        result = flaky_function()
        
        self.assertEqual(result, "success")
        self.assertEqual(self.call_count, 2)
        self._add_result("transient_errors_decorator", True, "Transient errors retried")
    
    def test_retry_preserves_function_metadata(self):
        """Test: Retry decorator preserves function metadata
        
        Given: Function with docstring and name
        When: Decorated with retry
        Then: Metadata preserved
        """
        @retry_with_backoff(max_retries=1)
        def test_function():
            """Test function docstring"""
            return "success"
        
        self.assertEqual(test_function.__name__, "test_function")
        self.assertIn("Test function docstring", test_function.__doc__)
        self._add_result("metadata_preserved", True, "Function metadata preserved")


if __name__ == "__main__":
    unittest.main(verbosity=2)


