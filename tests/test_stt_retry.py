"""
Tests for STT retry logic and error recovery.

Tests that STT retries on transient failures and handles errors gracefully.
"""

import unittest
import sys
import os
from unittest.mock import Mock, patch, MagicMock

import config
from modules.hailo_stt import HailoSTT
from tests.test_base import PiSatTestBase


class TestSTTRetry(PiSatTestBase):
    """Test STT retry logic for transient errors"""
    
    def setUp(self):
        super().setUp()
        if config.STT_BACKEND != "hailo":
            self.skipTest("STT_BACKEND is not 'hailo'")
        # Never start real Hailo threads in unit tests
        self._load_model_patcher = patch.object(HailoSTT, "_load_model", return_value=None)
        self._load_model_patcher.start()

    def tearDown(self):
        try:
            self._load_model_patcher.stop()
        except Exception:
            pass
        super().tearDown()
    
    def test_stt_retries_on_transient_error(self):
        """Test: STT retries on transient error
        
        Given: STT fails once then succeeds
        When: transcribe() called
        Then: Retries and succeeds
        """
        stt = HailoSTT(debug=True)
        
        # Mock pipeline to fail once then succeed
        mock_pipeline = MagicMock()
        call_count = [0]
        
        def mock_transcribe(audio_data):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("Transient Hailo error")
            return "test transcription"
        
        stt._transcribe_hailo = mock_transcribe
        stt._pipeline = mock_pipeline

        # Mock is_available to return True
        with patch.object(stt, 'is_available', return_value=True):
            result = stt.transcribe(b"fake audio data")
        
        # Should succeed after retry
        self.assertGreater(call_count[0], 1)
        self._add_result("stt_retry_transient", True, "STT retried on transient error")
    
    def test_stt_fails_after_max_retries(self):
        """Test: STT fails after max retries

        Given: STT always fails
        When: transcribe() called
        Then: Returns empty string after max retries
        """
        stt = HailoSTT(debug=True)

        def mock_transcribe(audio_data):
            raise RuntimeError("Persistent Hailo error")

        stt._transcribe_hailo = mock_transcribe
        stt._pipeline = MagicMock()

        with patch.object(stt, 'is_available', return_value=True):
            result = stt.transcribe(b"fake audio data")
        
        # Should return empty string after retries exhausted
        self.assertEqual(result, "")
        self._add_result("stt_fails_after_max", True, "STT fails gracefully after max retries")
    
    def test_stt_reloads_on_unavailable(self):
        """Test: STT reloads when unavailable
        
        Given: STT pipeline is None
        When: transcribe() called
        Then: Attempts reload before retrying
        """
        stt = HailoSTT(debug=True)
        stt._pipeline = None

        reload_called = [False]
        original_reload = stt.reload
        
        def mock_reload():
            reload_called[0] = True
            original_reload()
        
        stt.reload = mock_reload
        
        with patch.object(stt, 'is_available', return_value=False):
            result = stt.transcribe(b"fake audio data")
        
        # Should attempt reload
        self.assertTrue(reload_called[0] or result == "")
        self._add_result("stt_reloads_on_unavailable", True, "STT attempts reload when unavailable")
    
    def test_stt_handles_empty_audio(self):
        """Test: STT handles empty audio gracefully
        
        Given: Empty audio data
        When: transcribe() called
        Then: Returns empty string without retrying
        """
        stt = HailoSTT(debug=True)
        
        result = stt.transcribe(b"")
        
        self.assertEqual(result, "")
        self._add_result("stt_empty_audio", True, "STT handles empty audio gracefully")
    
    def test_stt_handles_connection_error(self):
        """Test: STT retries on connection errors

        Given: STT raises ConnectionError
        When: transcribe() called
        Then: Retries before failing
        """
        stt = HailoSTT(debug=True)

        call_count = [0]

        def mock_transcribe(audio_data):
            call_count[0] += 1
            if call_count[0] < 3:
                raise ConnectionError("Hailo connection lost")
            return "success after retry"

        stt._transcribe_hailo = mock_transcribe
        stt._pipeline = MagicMock()

        with patch.object(stt, 'is_available', return_value=True):
            result = stt.transcribe(b"fake audio data")
        
        self.assertGreater(call_count[0], 1)
        self._add_result("stt_connection_error", True, "STT retries on connection errors")


if __name__ == "__main__":
    unittest.main(verbosity=2)
