"""Audio file I/O utilities

Shared utilities for reading and writing audio files in WAV format.
Following KISS and DRY principles - extracted from hailo_stt.py and tests/test_utils.py.
"""

import wave
import numpy as np
from pathlib import Path


def to_int16(samples):
    """
    Convert audio samples to int16 format, handling clipping.

    Args:
        samples: Audio samples as numpy array or compatible type
                 - int16: Returned as-is
                 - float: Clipped to [-1.0, 1.0] and scaled to int16 range
                 - other: Converted to int16

    Returns:
        numpy.ndarray: Audio samples as int16

    Example:
        >>> float_audio = np.array([0.5, -0.3, 1.2])
        >>> int_audio = to_int16(float_audio)
        >>> int_audio
        array([16383, -9830, 32767], dtype=int16)
    """
    arr = np.asarray(samples)

    if arr.dtype == np.int16:
        return arr

    if np.issubdtype(arr.dtype, np.floating):
        # Clip to valid range and scale to int16
        arr = np.clip(arr, -1.0, 1.0)
        return (arr * 32767.0).astype(np.int16)

    return arr.astype(np.int16)


def write_wav_int16(path, samples, sample_rate):
    """
    Write int16 audio samples to WAV file.

    Args:
        path: Output file path (str or Path)
        samples: Audio samples (will be converted to int16 if needed)
        sample_rate: Sample rate in Hz (e.g., 16000, 48000)

    Example:
        >>> audio = np.sin(2 * np.pi * 440 * np.linspace(0, 1, 16000))
        >>> write_wav_int16("tone.wav", audio, 16000)
    """
    samples_int16 = to_int16(samples)

    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)  # Mono
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(int(sample_rate))
        wf.writeframes(samples_int16.tobytes())


def read_wav_mono_int16(path):
    """
    Read WAV file as mono int16 samples.

    Args:
        path: Input WAV file path (str or Path)

    Returns:
        tuple: (samples, sample_rate)
               - samples: numpy.ndarray of int16 samples
               - sample_rate: int, sample rate in Hz

    Raises:
        AssertionError: If file is not mono or not 16-bit

    Example:
        >>> samples, rate = read_wav_mono_int16("audio.wav")
        >>> print(f"Loaded {len(samples)} samples at {rate} Hz")
    """
    with wave.open(str(path), "rb") as wf:
        assert wf.getnchannels() == 1, "Expected mono audio"
        assert wf.getsampwidth() == 2, "Expected 16-bit audio"

        sample_rate = wf.getframerate()
        frames = wf.readframes(wf.getnframes())
        samples = np.frombuffer(frames, dtype=np.int16)

        return samples, sample_rate
