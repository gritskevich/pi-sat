#!/usr/bin/env python3
"""
VAD Calibration Tool - Analyze audio levels and tune silence detection

Usage: python scripts/calibrate_vad.py

Helps you:
1. Measure ambient noise floor
2. Visualize speech energy levels
3. Find optimal silence detection thresholds
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pyaudio
import numpy as np
import time
import config
from modules.logging_utils import setup_logger, log_info, log_success, log_warning

# Setup logger
logger = setup_logger(__name__)

def analyze_audio_levels(duration=10.0):
    """
    Record audio and analyze energy levels.

    Shows:
    - Noise floor (ambient noise)
    - Speech peaks
    - Recommended thresholds
    """
    log_info(logger, "=" * 60)
    log_info(logger, "VAD CALIBRATION TOOL")
    log_info(logger, "=" * 60)
    log_info(logger, f"Recording for {duration}s...")
    log_info(logger, "1. First 2s: Stay SILENT (measures noise floor)")
    log_info(logger, "2. Then: Talk with pauses (measures speech levels)")
    log_info(logger, "=" * 60)
    log_info(logger, "")

    p = pyaudio.PyAudio()
    stream = p.open(
        format=getattr(pyaudio, config.FORMAT),
        channels=config.CHANNELS,
        rate=config.RATE,
        input=True,
        frames_per_buffer=config.CHUNK
    )

    energy_samples = []
    timestamps = []
    start_time = time.time()

    try:
        while time.time() - start_time < duration:
            data = stream.read(config.CHUNK, exception_on_overflow=False)
            audio = np.frombuffer(data, dtype=np.int16)

            # Calculate RMS energy
            energy = np.sqrt(np.mean(audio.astype(np.float32) ** 2))
            energy_samples.append(energy)
            timestamps.append(time.time() - start_time)

            # Real-time feedback (print to stderr to not interfere with logging)
            elapsed = time.time() - start_time
            if elapsed < 2.0:
                print(f"\r🔇 Silence phase: {energy:.1f} RMS   ", end='', flush=True, file=sys.stderr)
            else:
                print(f"\r🗣️  Speech phase: {energy:.1f} RMS   ", end='', flush=True, file=sys.stderr)

    except KeyboardInterrupt:
        log_info(logger, "\n\nStopped by user")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()

    print("\n", file=sys.stderr)  # Clear the line
    log_info(logger, "=" * 60)
    log_info(logger, "ANALYSIS RESULTS")
    log_info(logger, "=" * 60)

    # Analyze noise floor (first 2 seconds)
    silence_duration = 2.0
    silence_samples = int((silence_duration / duration) * len(energy_samples))
    noise_samples = energy_samples[:silence_samples]
    speech_samples = energy_samples[silence_samples:]

    if noise_samples:
        noise_floor = np.median(noise_samples)
        noise_max = np.max(noise_samples)
        log_info(logger, f"📊 Noise Floor (median): {noise_floor:.1f} RMS")
        log_info(logger, f"📊 Noise Max: {noise_max:.1f} RMS")
    else:
        noise_floor = 0
        log_warning(logger, "No noise floor data")

    if speech_samples:
        speech_median = np.median(speech_samples)
        speech_max = np.max(speech_samples)
        speech_min = np.min(speech_samples)
        log_info(logger, f"🗣️  Speech Median: {speech_median:.1f} RMS")
        log_info(logger, f"🗣️  Speech Max: {speech_max:.1f} RMS")
        log_info(logger, f"🗣️  Speech Min: {speech_min:.1f} RMS")
    else:
        log_warning(logger, "No speech data")

    log_info(logger, "")
    log_info(logger, "=" * 60)
    log_info(logger, "RECOMMENDATIONS")
    log_info(logger, "=" * 60)

    if noise_floor > 0 and speech_samples:
        # Calculate signal-to-noise ratio
        snr = speech_median / noise_floor if noise_floor > 0 else 0
        log_info(logger, f"📈 Signal-to-Noise Ratio: {snr:.2f}x")
        log_info(logger, "")

        # Recommend threshold multiplier
        if snr > 5:
            recommended_multiplier = 2.0
            log_success(logger, "Good SNR - Use multiplier: 2.0x")
        elif snr > 2:
            recommended_multiplier = 1.5
            log_warning(logger, "Moderate SNR - Use multiplier: 1.5x")
        else:
            recommended_multiplier = 1.3
            log_warning(logger, "Low SNR - Use multiplier: 1.3x (noisy environment)")

        log_info(logger, f"   Speech threshold: {noise_floor * recommended_multiplier:.1f} RMS")
        log_info(logger, "")

        # Recommend silence duration
        if snr > 5:
            silence_duration = 0.8
        elif snr > 2:
            silence_duration = 1.0
        else:
            silence_duration = 1.2

        log_info(logger, f"⏱️  Recommended silence duration: {silence_duration}s")

    log_info(logger, "=" * 60)

    # Distribution analysis
    log_info(logger, "")
    log_info(logger, "ENERGY DISTRIBUTION:")
    bins = [0, 50, 100, 200, 500, 1000, 5000, 10000]
    hist, _ = np.histogram(energy_samples, bins=bins)
    for i in range(len(bins) - 1):
        bar = "█" * int(hist[i] / max(hist) * 40) if max(hist) > 0 else ""
        log_info(logger, f"  {bins[i]:>5} - {bins[i+1]:>5}: {bar} ({hist[i]})")

    log_info(logger, "")
    log_info(logger, "=" * 60)
    log_info(logger, "TIPS:")
    log_info(logger, "- Lower multiplier = more sensitive (detects softer speech)")
    log_info(logger, "- Higher multiplier = less sensitive (rejects noise)")
    log_info(logger, "- Longer silence = waits more before ending")
    log_info(logger, "- Shorter silence = cuts off faster")
    log_info(logger, "=" * 60)

if __name__ == "__main__":
    analyze_audio_levels()
