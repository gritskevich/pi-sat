#!/usr/bin/env python3
"""Cut recorded audio into individual wake word samples using energy-based VAD."""
import sys
import wave
import struct
import math
from pathlib import Path

def read_wav(path):
    """Read WAV file, return (samples, rate)."""
    with wave.open(str(path), 'rb') as wf:
        rate = wf.getframerate()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)
        samples = list(struct.unpack(f'<{n_frames}h', raw))
    return samples, rate

def write_wav(path, samples, rate):
    """Write samples to WAV file."""
    with wave.open(str(path), 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(struct.pack(f'<{len(samples)}h', *samples))

def compute_rms(samples):
    """Compute RMS energy."""
    if not samples:
        return 0
    return math.sqrt(sum(s*s for s in samples) / len(samples))

def find_segments(samples, rate, min_duration=0.5, max_duration=3.0,
                  silence_threshold=500, min_silence=0.3):
    """Find speech segments using simple energy-based VAD."""
    frame_size = int(rate * 0.02)  # 20ms frames
    min_frames = int(min_duration / 0.02)
    max_frames = int(max_duration / 0.02)
    silence_frames = int(min_silence / 0.02)

    # Compute frame energies
    energies = []
    for i in range(0, len(samples) - frame_size, frame_size):
        frame = samples[i:i + frame_size]
        energies.append(compute_rms(frame))

    # Find speech regions
    segments = []
    in_speech = False
    start = 0
    silence_count = 0

    for i, energy in enumerate(energies):
        if energy > silence_threshold:
            if not in_speech:
                start = max(0, i - 5)  # Include 100ms before
                in_speech = True
            silence_count = 0
        else:
            if in_speech:
                silence_count += 1
                if silence_count >= silence_frames:
                    end = min(len(energies), i + 5)  # Include 100ms after
                    length = end - start
                    if min_frames <= length <= max_frames:
                        segments.append((start * frame_size, end * frame_size))
                    in_speech = False

    # Handle last segment
    if in_speech:
        end = len(energies)
        length = end - start
        if min_frames <= length <= max_frames:
            segments.append((start * frame_size, end * frame_size))

    return segments

def resample_16k(samples, src_rate):
    """Simple resample to 16kHz if needed."""
    if src_rate == 16000:
        return samples
    ratio = 16000 / src_rate
    new_len = int(len(samples) * ratio)
    resampled = []
    for i in range(new_len):
        src_idx = i / ratio
        idx = int(src_idx)
        if idx >= len(samples) - 1:
            resampled.append(samples[-1])
        else:
            frac = src_idx - idx
            resampled.append(int(samples[idx] * (1 - frac) + samples[idx + 1] * frac))
    return resampled

def main():
    if len(sys.argv) < 2:
        print("Usage: python cut_wake_samples.py <recording.wav> [--threshold N]")
        print("\nOptions:")
        print("  --threshold N   Energy threshold (default: 500, lower = more sensitive)")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    threshold = 500

    if "--threshold" in sys.argv:
        idx = sys.argv.index("--threshold")
        threshold = int(sys.argv[idx + 1])

    if not input_path.exists():
        print(f"File not found: {input_path}")
        sys.exit(1)

    output_dir = input_path.parent / f"{input_path.stem}_clips"
    output_dir.mkdir(exist_ok=True)

    print(f"Reading: {input_path}")
    samples, rate = read_wav(input_path)
    print(f"  Duration: {len(samples)/rate:.1f}s at {rate}Hz")
    print(f"  Threshold: {threshold}")

    print("\nFinding segments...")
    segments = find_segments(samples, rate, silence_threshold=threshold)
    print(f"  Found {len(segments)} potential clips")

    if not segments:
        print("\nNo segments found. Try lowering --threshold (e.g., --threshold 300)")
        sys.exit(1)

    print(f"\nSaving clips to: {output_dir}/")
    for i, (start, end) in enumerate(segments):
        clip = samples[start:end]

        # Resample to 16kHz if needed
        if rate != 16000:
            clip = resample_16k(clip, rate)

        duration = len(clip) / 16000
        output_file = output_dir / f"alexa_custom_{i+1:03d}.wav"
        write_wav(output_file, clip, 16000)
        print(f"  [{i+1:2d}] {output_file.name} ({duration:.2f}s)")

    print(f"\n✅ Created {len(segments)} clips in {output_dir}/")
    print("\nNext steps:")
    print("  1. Listen to clips and delete bad ones")
    print("  2. Use clips to train/fine-tune wake word model")

if __name__ == "__main__":
    main()
