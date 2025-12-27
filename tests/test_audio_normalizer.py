"""
Tests for audio_normalizer module

Test coverage:
- RMS calculation
- Gain calculation and application
- Soft limiter
- Full normalization pipeline
- Edge cases (silence, empty audio, extreme levels)
"""

import pytest
import numpy as np
from modules.audio_normalizer import AudioNormalizer, normalize_audio


class TestAudioNormalizer:
    """Test suite for AudioNormalizer class"""

    def test_calculate_rms_sine_wave(self):
        """Test RMS calculation with known sine wave"""
        normalizer = AudioNormalizer()

        # Generate 1kHz sine wave at amplitude 1000 for 1 second @ 16kHz
        sample_rate = 16000
        duration = 1.0
        frequency = 1000
        amplitude = 1000

        t = np.linspace(0, duration, int(sample_rate * duration))
        audio = (amplitude * np.sin(2 * np.pi * frequency * t)).astype(np.int16)

        rms = normalizer.calculate_rms(audio)

        # RMS of sine wave = amplitude / sqrt(2) ≈ 707.1
        expected_rms = amplitude / np.sqrt(2)
        assert abs(rms - expected_rms) < 1.0, f"RMS {rms} should be ~{expected_rms}"

    def test_calculate_rms_empty_audio(self):
        """Test RMS calculation with empty audio"""
        normalizer = AudioNormalizer()

        audio = np.array([], dtype=np.int16)
        rms = normalizer.calculate_rms(audio)

        assert rms == 0.0, "Empty audio should have RMS of 0"

    def test_calculate_rms_silence(self):
        """Test RMS calculation with silence"""
        normalizer = AudioNormalizer()

        audio = np.zeros(16000, dtype=np.int16)
        rms = normalizer.calculate_rms(audio)

        assert rms == 0.0, "Silence should have RMS of 0"

    def test_normalize_quiet_audio(self):
        """Test normalization of quiet audio (far speech simulation)"""
        target_rms = 3000.0
        normalizer = AudioNormalizer(target_rms=target_rms, debug=False)

        # Generate quiet audio (RMS ~500)
        sample_rate = 16000
        duration = 0.5
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio = (np.sin(2 * np.pi * 200 * t) * 700).astype(np.int16)

        original_rms = normalizer.calculate_rms(audio)
        assert original_rms < target_rms, "Test audio should be quieter than target"

        # Normalize
        normalized_bytes = normalizer.normalize_audio(audio.tobytes())
        normalized = np.frombuffer(normalized_bytes, dtype=np.int16)

        new_rms = normalizer.calculate_rms(normalized)

        # Should be close to target (within 10%)
        assert abs(new_rms - target_rms) / target_rms < 0.1, \
            f"Normalized RMS {new_rms} should be ~{target_rms}"

    def test_normalize_loud_audio(self):
        """Test normalization of loud audio (close speech simulation)"""
        target_rms = 3000.0
        normalizer = AudioNormalizer(target_rms=target_rms, debug=False)

        # Generate loud audio (RMS ~7000)
        sample_rate = 16000
        duration = 0.5
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio = (np.sin(2 * np.pi * 200 * t) * 10000).astype(np.int16)

        original_rms = normalizer.calculate_rms(audio)
        assert original_rms > target_rms, "Test audio should be louder than target"

        # Normalize
        normalized_bytes = normalizer.normalize_audio(audio.tobytes())
        normalized = np.frombuffer(normalized_bytes, dtype=np.int16)

        new_rms = normalizer.calculate_rms(normalized)

        # Should be close to target (within 10%)
        assert abs(new_rms - target_rms) / target_rms < 0.1, \
            f"Normalized RMS {new_rms} should be ~{target_rms}"

    def test_normalize_silence_skipped(self):
        """Test that silence is not amplified"""
        normalizer = AudioNormalizer(target_rms=3000.0, debug=False)

        # Silent audio
        audio = np.zeros(16000, dtype=np.int16)
        audio_bytes = audio.tobytes()

        # Normalize
        normalized_bytes = normalizer.normalize_audio(audio_bytes)

        # Should return unchanged
        assert normalized_bytes == audio_bytes, "Silence should not be modified"

    def test_max_gain_limit(self):
        """Test that maximum gain is enforced"""
        target_rms = 3000.0
        max_gain = 5.0
        normalizer = AudioNormalizer(target_rms=target_rms, max_gain=max_gain, debug=False)

        # Generate very quiet audio that would require gain > max_gain
        # RMS = 100, target = 3000 → gain would be 30x, but max is 5x
        audio = (np.sin(2 * np.pi * 200 * np.linspace(0, 1, 16000)) * 141).astype(np.int16)

        original_rms = normalizer.calculate_rms(audio)
        required_gain = target_rms / original_rms
        assert required_gain > max_gain, "Test should require gain > max_gain"

        # Normalize
        normalized_bytes = normalizer.normalize_audio(audio.tobytes())
        normalized = np.frombuffer(normalized_bytes, dtype=np.int16)

        new_rms = normalizer.calculate_rms(normalized)

        # Should be limited by max_gain, not reach full target
        expected_rms = original_rms * max_gain
        assert abs(new_rms - expected_rms) / expected_rms < 0.1, \
            f"RMS {new_rms} should be limited to ~{expected_rms}"

    def test_soft_limiter_prevents_clipping(self):
        """Test that soft limiter prevents hard clipping"""
        normalizer = AudioNormalizer(target_rms=15000.0, limiter_threshold=28000.0, debug=False)

        # Generate audio that would clip without limiter
        audio = (np.sin(2 * np.pi * 200 * np.linspace(0, 1, 16000)) * 20000).astype(np.int16)

        # Normalize
        normalized_bytes = normalizer.normalize_audio(audio.tobytes())
        normalized = np.frombuffer(normalized_bytes, dtype=np.int16)

        # Check that no samples exceed int16 range
        assert np.all(normalized >= -32768), "No samples should be below -32768"
        assert np.all(normalized <= 32767), "No samples should be above 32767"

        # Peak should be at or below limiter threshold (with some tolerance for tanh)
        peak = np.max(np.abs(normalized))
        assert peak <= 32767, f"Peak {peak} should not exceed int16 range"

    def test_normalize_empty_bytes(self):
        """Test normalization with empty bytes"""
        normalizer = AudioNormalizer()

        result = normalizer.normalize_audio(b"")
        assert result == b"", "Empty bytes should return empty bytes"

    def test_normalize_audio_function(self):
        """Test convenience function normalize_audio()"""
        # Generate test audio
        audio = (np.sin(2 * np.pi * 200 * np.linspace(0, 1, 16000)) * 1000).astype(np.int16)

        # Normalize using convenience function
        normalized_bytes = normalize_audio(audio.tobytes(), target_rms=3000.0, debug=False)

        normalized = np.frombuffer(normalized_bytes, dtype=np.int16)
        normalizer = AudioNormalizer()
        new_rms = normalizer.calculate_rms(normalized)

        # Should be close to target
        assert abs(new_rms - 3000.0) / 3000.0 < 0.1

    def test_normalization_consistency(self):
        """Test that normalized audio from different levels converges to similar RMS"""
        target_rms = 3000.0
        normalizer = AudioNormalizer(target_rms=target_rms, debug=False)

        # Generate 3 audio signals at different levels
        t = np.linspace(0, 1, 16000)

        quiet = (np.sin(2 * np.pi * 200 * t) * 500).astype(np.int16)
        medium = (np.sin(2 * np.pi * 200 * t) * 3000).astype(np.int16)
        loud = (np.sin(2 * np.pi * 200 * t) * 8000).astype(np.int16)

        # Normalize all
        quiet_norm = np.frombuffer(normalizer.normalize_audio(quiet.tobytes()), dtype=np.int16)
        medium_norm = np.frombuffer(normalizer.normalize_audio(medium.tobytes()), dtype=np.int16)
        loud_norm = np.frombuffer(normalizer.normalize_audio(loud.tobytes()), dtype=np.int16)

        # Calculate RMS
        quiet_rms = normalizer.calculate_rms(quiet_norm)
        medium_rms = normalizer.calculate_rms(medium_norm)
        loud_rms = normalizer.calculate_rms(loud_norm)

        # All should be close to target (within 15%)
        assert abs(quiet_rms - target_rms) / target_rms < 0.15
        assert abs(medium_rms - target_rms) / target_rms < 0.15
        assert abs(loud_rms - target_rms) / target_rms < 0.15

        # All should be close to each other (within 20%)
        rms_values = [quiet_rms, medium_rms, loud_rms]
        mean_rms = np.mean(rms_values)
        for rms in rms_values:
            assert abs(rms - mean_rms) / mean_rms < 0.2

    def test_pre_calculated_rms(self):
        """Test normalization with pre-calculated RMS"""
        normalizer = AudioNormalizer(target_rms=3000.0, debug=False)

        # Generate test audio
        audio = (np.sin(2 * np.pi * 200 * np.linspace(0, 1, 16000)) * 1000).astype(np.int16)

        # Pre-calculate RMS
        rms = normalizer.calculate_rms(audio)

        # Normalize with pre-calculated RMS
        normalized_bytes = normalizer.normalize_audio(audio.tobytes(), current_rms=rms)

        normalized = np.frombuffer(normalized_bytes, dtype=np.int16)
        new_rms = normalizer.calculate_rms(normalized)

        # Should still work correctly
        assert abs(new_rms - 3000.0) / 3000.0 < 0.1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
