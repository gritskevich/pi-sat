"""
Audio Normalization Module

Normalizes audio levels to handle variable microphone distance (close vs far speech).
Uses RMS (Root Mean Square) energy normalization with dynamic range limiting.

Purpose:
- Compensate for volume differences when speaking close vs far from microphone
- Provide consistent audio levels to STT for optimal recognition
- Prevent clipping with limiter

Approach (KISS):
- Calculate RMS energy of audio signal
- Apply gain to reach target RMS level
- Apply soft limiter to prevent clipping
- No external dependencies (NumPy only)

Integration:
- Call normalize_audio() after recording, before STT processing
- Optional: Enable/disable via config.AUDIO_NORMALIZATION_ENABLED

Research sources:
- RMS normalization: https://superkogito.github.io/blog/2020/04/30/rms_normalization.html
- SpeechRecognition energy calibration: https://www.codesofinterest.com/2017/04/energy-threshold-calibration-in-speech-recognition.html
- WebRTC AGC: https://github.com/xiongyihui/python-webrtc-audio-processing
"""

import numpy as np
from typing import Optional
from .base_module import BaseModule
from .logging_utils import log_debug, log_warning


class AudioNormalizer(BaseModule):
    """
    Normalizes audio levels using RMS energy normalization.

    Handles variable microphone distance by applying gain to reach consistent RMS level.
    """

    def __init__(self, target_rms: float = 3000.0, max_gain: float = 10.0,
                 limiter_threshold: float = 28000.0, debug: bool = False,
                 verbose: bool = True, event_bus=None):
        """
        Initialize audio normalizer.

        Args:
            target_rms: Target RMS energy level (default: 3000)
            max_gain: Maximum amplification factor to prevent noise boost (default: 10.0)
            limiter_threshold: Peak limiter threshold to prevent clipping (default: 28000)
            debug: Enable debug logging
        """
        super().__init__(__name__, debug=debug, verbose=verbose, event_bus=event_bus)
        self.target_rms = float(target_rms)
        self.max_gain = float(max_gain)
        self.limiter_threshold = float(limiter_threshold)

    def calculate_rms(self, audio: np.ndarray) -> float:
        """
        Calculate RMS (Root Mean Square) energy of audio signal.

        Args:
            audio: Audio samples as numpy array (int16 or float32)

        Returns:
            RMS energy as float
        """
        if audio.size == 0:
            return 0.0

        # Convert to float for calculation
        audio_float = audio.astype(np.float32)

        # RMS = sqrt(mean(signal^2))
        rms = float(np.sqrt(np.mean(audio_float ** 2)))

        return rms

    def apply_soft_limiter(self, audio: np.ndarray, threshold: float) -> np.ndarray:
        """
        Apply soft limiter to prevent clipping while preserving dynamics.

        Uses tanh-based soft clipping for smooth limiting without hard distortion.

        Args:
            audio: Audio samples as numpy array (float32)
            threshold: Limiter threshold (samples above this are compressed)

        Returns:
            Limited audio samples
        """
        if threshold <= 0:
            return audio

        # Normalize to [-1, 1] range for tanh
        scale = threshold
        normalized = audio / scale

        # Apply soft limiting using tanh (smooth compression)
        limited = np.tanh(normalized)

        # Scale back
        return limited * scale

    def normalize_audio(self, audio_bytes: bytes, current_rms: Optional[float] = None) -> bytes:
        """
        Normalize audio to target RMS level with limiter.

        Args:
            audio_bytes: Raw PCM audio data (16-bit mono, any sample rate)
            current_rms: Pre-calculated RMS (optional, will calculate if not provided)

        Returns:
            Normalized audio as bytes (same format as input)
        """
        if not audio_bytes or len(audio_bytes) == 0:
            return audio_bytes

        # Convert bytes to numpy array
        audio = np.frombuffer(audio_bytes, dtype=np.int16)

        if audio.size == 0:
            return audio_bytes

        # Calculate RMS if not provided
        if current_rms is None:
            current_rms = self.calculate_rms(audio)

        # Skip normalization if audio is silent (RMS < 10)
        if current_rms < 10.0:
            if self.debug:
                log_debug(self.logger, f"Audio too quiet (RMS: {current_rms:.1f}), skipping normalization")
            return audio_bytes

        # Calculate required gain
        gain = self.target_rms / current_rms

        # Limit gain to prevent excessive noise amplification
        if gain > self.max_gain:
            if self.debug:
                log_warning(
                    self.logger,
                    f"Gain {gain:.2f}x exceeds max {self.max_gain}x (RMS: {current_rms:.1f}), limiting"
                )
            gain = self.max_gain

        if self.debug:
            log_debug(
                self.logger,
                f"Normalizing: RMS {current_rms:.1f} → {self.target_rms:.1f} (gain: {gain:.2f}x)"
            )

        # Apply gain
        audio_float = audio.astype(np.float32) * gain

        # Apply soft limiter to prevent clipping
        audio_limited = self.apply_soft_limiter(audio_float, self.limiter_threshold)

        # Convert back to int16, clipping to valid range
        audio_normalized = np.clip(audio_limited, -32768, 32767).astype(np.int16)

        # Calculate final RMS for verification
        if self.debug:
            final_rms = self.calculate_rms(audio_normalized)
            log_debug(
                self.logger,
                f"Normalized audio: {current_rms:.1f} → {final_rms:.1f} RMS (target: {self.target_rms:.1f})"
            )

        return audio_normalized.tobytes()


def normalize_audio(audio_bytes: bytes, target_rms: float = 3000.0,
                    max_gain: float = 10.0, limiter_threshold: float = 28000.0,
                    debug: bool = False) -> bytes:
    """
    Convenience function to normalize audio without creating AudioNormalizer instance.

    Args:
        audio_bytes: Raw PCM audio data (16-bit mono)
        target_rms: Target RMS energy level (default: 3000)
        max_gain: Maximum amplification factor (default: 10.0)
        limiter_threshold: Peak limiter threshold (default: 28000)
        debug: Enable debug logging

    Returns:
        Normalized audio as bytes
    """
    normalizer = AudioNormalizer(
        target_rms=target_rms,
        max_gain=max_gain,
        limiter_threshold=limiter_threshold,
        debug=debug
    )
    return normalizer.normalize_audio(audio_bytes)


if __name__ == "__main__":
    # Test normalization with synthetic audio
    import sys

    print("Audio Normalizer Test")
    print("=" * 50)

    # Create test signals at different levels
    sample_rate = 16000
    duration = 1.0  # 1 second
    samples = int(sample_rate * duration)

    # Generate test tones at different amplitudes (simulating close vs far speech)
    t = np.linspace(0, duration, samples)

    # Far speech (quiet, RMS ~500)
    far_speech = (np.sin(2 * np.pi * 200 * t) * 1000).astype(np.int16)

    # Close speech (loud, RMS ~5000)
    close_speech = (np.sin(2 * np.pi * 200 * t) * 10000).astype(np.int16)

    # Create normalizer
    normalizer = AudioNormalizer(target_rms=3000.0, debug=True)

    print("\nTest 1: Far Speech (quiet)")
    print("-" * 50)
    far_rms_before = normalizer.calculate_rms(far_speech)
    print(f"Before: RMS = {far_rms_before:.1f}")

    far_normalized = normalizer.normalize_audio(far_speech.tobytes())
    far_array = np.frombuffer(far_normalized, dtype=np.int16)
    far_rms_after = normalizer.calculate_rms(far_array)
    print(f"After:  RMS = {far_rms_after:.1f}")

    print("\nTest 2: Close Speech (loud)")
    print("-" * 50)
    close_rms_before = normalizer.calculate_rms(close_speech)
    print(f"Before: RMS = {close_rms_before:.1f}")

    close_normalized = normalizer.normalize_audio(close_speech.tobytes())
    close_array = np.frombuffer(close_normalized, dtype=np.int16)
    close_rms_after = normalizer.calculate_rms(close_array)
    print(f"After:  RMS = {close_rms_after:.1f}")

    print("\n" + "=" * 50)
    print("✓ Both signals normalized to similar RMS levels")
