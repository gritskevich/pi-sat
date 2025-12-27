#!/usr/bin/env python3
"""
Tests for SpeechRecorder adaptive VAD functionality

Tests the record_from_stream() method with energy-based silence detection.
"""

import unittest
import numpy as np
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from modules.speech_recorder import SpeechRecorder
import config


class MockStream:
    """Mock PyAudio stream for testing"""
    def __init__(self, audio_chunks):
        self.audio_chunks = audio_chunks
        self.index = 0

    def read(self, chunk_size, exception_on_overflow=False):
        if self.index >= len(self.audio_chunks):
            # Return silence after chunks exhausted
            return np.zeros(chunk_size, dtype=np.int16).tobytes()

        chunk = self.audio_chunks[self.index]
        self.index += 1
        return chunk


@unittest.skip("Tests for record_from_stream which was removed during stream optimization refactoring")
class TestSpeechRecorderAdaptive(unittest.TestCase):
    """Test suite for adaptive VAD recording"""

    def setUp(self):
        """Set up test fixtures"""
        self.recorder = SpeechRecorder(debug=False)
        # Make tests deterministic: energy-based detection drives speech/non-speech,
        # so force the WebRTC VAD leg to "True".
        self.recorder.vad.is_speech = lambda frame_bytes, sample_rate: True  # noqa: ARG005

    def generate_audio_chunk(self, duration_ms=30, amplitude=0, sample_rate=48000):
        """
        Generate an audio chunk with specified amplitude.

        Args:
            duration_ms: Duration in milliseconds
            amplitude: Amplitude (0 = silence, higher = louder)
            sample_rate: Sample rate

        Returns:
            Audio chunk as bytes
        """
        samples = int(sample_rate * duration_ms / 1000)
        if amplitude == 0:
            audio = np.zeros(samples, dtype=np.int16)
        else:
            # Generate noise/speech-like audio
            audio = (np.random.randn(samples) * amplitude).astype(np.int16)
        return audio.tobytes()

    def test_noise_floor_calibration(self):
        """Test that noise floor is correctly calibrated"""
        # Create chunks: 10 quiet chunks (calibration), then speech
        chunks = []

        # Calibration phase - low noise
        for _ in range(10):
            chunks.append(self.generate_audio_chunk(amplitude=100))

        # Speech phase - high amplitude
        for _ in range(20):
            chunks.append(self.generate_audio_chunk(amplitude=1000))

        # Silence to end
        for _ in range(40):
            chunks.append(self.generate_audio_chunk(amplitude=0))

        stream = MockStream(chunks)

        # Record should detect speech and end on silence
        audio_data = self.recorder.record_from_stream(stream, input_rate=48000, max_duration=5.0)

        # Should have recorded something
        self.assertGreater(len(audio_data), 0)

    def test_speech_detection(self):
        """Test that speech is correctly detected above noise floor"""
        chunks = []

        # Calibration - quiet
        for _ in range(10):
            chunks.append(self.generate_audio_chunk(amplitude=50))

        # Speech - loud
        for _ in range(30):
            chunks.append(self.generate_audio_chunk(amplitude=500))

        # Silence - end
        for _ in range(40):
            chunks.append(self.generate_audio_chunk(amplitude=0))

        stream = MockStream(chunks)
        audio_data = self.recorder.record_from_stream(stream, input_rate=48000, max_duration=5.0)

        # Should have captured speech
        self.assertGreater(len(audio_data), 0)

    def test_silence_ending(self):
        """Test that recording ends after silence threshold"""
        chunks = []

        # Calibration
        for _ in range(10):
            chunks.append(self.generate_audio_chunk(amplitude=100))

        # Speech
        for _ in range(20):
            chunks.append(self.generate_audio_chunk(amplitude=1000))

        # Long silence (should trigger end)
        for _ in range(50):
            chunks.append(self.generate_audio_chunk(amplitude=0))

        stream = MockStream(chunks)

        import time
        start = time.time()
        audio_data = self.recorder.record_from_stream(stream, input_rate=48000, max_duration=10.0)
        duration = time.time() - start

        # Should end before max_duration due to silence detection
        self.assertLess(duration, 5.0)
        self.assertGreater(len(audio_data), 0)

    def test_max_duration_cutoff(self):
        """Test that recording stops at max duration"""
        # Create continuous speech (no silence)
        chunks = []
        for _ in range(500):  # Many chunks
            chunks.append(self.generate_audio_chunk(amplitude=1000))

        stream = MockStream(chunks)

        import time
        start = time.time()
        audio_data = self.recorder.record_from_stream(stream, input_rate=48000, max_duration=1.0)
        duration = time.time() - start

        # Should stop at max_duration
        self.assertLessEqual(duration, 1.5)  # Allow some tolerance

    def test_minimum_speech_duration(self):
        """Test that very short speech bursts don't end recording prematurely"""
        chunks = []

        # Calibration
        for _ in range(10):
            chunks.append(self.generate_audio_chunk(amplitude=100))

        # Very short speech burst
        for _ in range(5):
            chunks.append(self.generate_audio_chunk(amplitude=1000))

        # Silence
        for _ in range(50):
            chunks.append(self.generate_audio_chunk(amplitude=0))

        stream = MockStream(chunks)
        audio_data = self.recorder.record_from_stream(stream, input_rate=48000, max_duration=5.0)

        # Recording might continue waiting for more speech
        # At minimum, calibration chunks should be captured
        self.assertGreater(len(audio_data), 0)

    def test_empty_stream(self):
        """Test handling of empty/silent stream"""
        chunks = []

        # Only silence
        for _ in range(100):
            chunks.append(self.generate_audio_chunk(amplitude=0))

        stream = MockStream(chunks)

        # Should handle gracefully
        audio_data = self.recorder.record_from_stream(stream, input_rate=48000, max_duration=2.0)

        # May return empty or just calibration frames
        self.assertIsInstance(audio_data, bytes)

    def test_config_parameters_respected(self):
        """Test that config parameters are used"""
        # Save original values
        original_multiplier = config.VAD_SPEECH_MULTIPLIER
        original_silence = config.VAD_SILENCE_DURATION

        try:
            # Set test values
            config.VAD_SPEECH_MULTIPLIER = 1.5
            config.VAD_SILENCE_DURATION = 0.5

            chunks = []
            for _ in range(10):
                chunks.append(self.generate_audio_chunk(amplitude=100))
            for _ in range(20):
                chunks.append(self.generate_audio_chunk(amplitude=800))
            for _ in range(20):
                chunks.append(self.generate_audio_chunk(amplitude=0))

            stream = MockStream(chunks)
            audio_data = self.recorder.record_from_stream(stream, input_rate=48000)

            # Should complete (parameters should be applied)
            self.assertIsInstance(audio_data, bytes)

        finally:
            # Restore original values
            config.VAD_SPEECH_MULTIPLIER = original_multiplier
            config.VAD_SILENCE_DURATION = original_silence

    def test_returns_16k_pcm(self):
        """record_from_stream() returns raw 16kHz int16 PCM bytes (no WAV header)."""
        chunks = []

        # Calibration
        for _ in range(10):
            chunks.append(self.generate_audio_chunk(amplitude=80))

        # Speech
        for _ in range(20):
            chunks.append(self.generate_audio_chunk(amplitude=800))

        # Silence
        for _ in range(40):
            chunks.append(self.generate_audio_chunk(amplitude=0))

        stream = MockStream(chunks)
        audio_data = self.recorder.record_from_stream(stream, input_rate=48000, max_duration=5.0)

        self.assertIsInstance(audio_data, bytes)
        self.assertEqual(len(audio_data) % 2, 0)  # int16 PCM

        frame_samples = int(16000 * (config.FRAME_DURATION / 1000.0))
        self.assertEqual(len(audio_data) % (frame_samples * 2), 0)


if __name__ == '__main__':
    unittest.main()
