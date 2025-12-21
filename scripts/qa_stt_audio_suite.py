#!/usr/bin/env python3
"""
QA tool for generated STT test audio.

Checks:
- WAV is 16 kHz mono PCM
- Expected pauses (encoded in filename) exist as silence runs

Filename conventions:
- alexa_pause_0.3s_<id>.wav
- mid_pause_0.8s_<id>.wav
- alexa_pause_0.3s_mid_pause_0.8s_<id>.wav
"""

from __future__ import annotations

import argparse
import re
import sys
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np


PAUSE_RE = re.compile(r"(?:^|_)((?:alexa|mid)_pause)_(\d+(?:\.\d+)?)s(?:_|\.wav$)")


@dataclass(frozen=True)
class WavInfo:
    path: Path
    rate: int
    channels: int
    sampwidth: int
    frames: int


def read_wav_int16(path: Path) -> tuple[WavInfo, np.ndarray]:
    with wave.open(str(path), "rb") as w:
        info = WavInfo(
            path=path,
            rate=w.getframerate(),
            channels=w.getnchannels(),
            sampwidth=w.getsampwidth(),
            frames=w.getnframes(),
        )
        raw = w.readframes(info.frames)

    if info.sampwidth != 2:
        raise ValueError(f"expected 16-bit PCM (sampwidth=2), got {info.sampwidth}")
    if info.channels != 1:
        raise ValueError(f"expected mono (channels=1), got {info.channels}")

    samples = np.frombuffer(raw, dtype=np.int16)
    return info, samples


def silence_runs(samples: np.ndarray, *, rate: int, threshold: int, min_silence_s: float) -> list[float]:
    silent = np.abs(samples) <= threshold
    if not np.any(silent):
        return []

    padded = np.concatenate([[False], silent, [False]])
    changes = np.flatnonzero(padded[1:] != padded[:-1])
    # changes pairs: start, end for True-runs in original `silent`
    durations: list[float] = []
    for start, end in zip(changes[0::2], changes[1::2]):
        dur = (end - start) / float(rate)
        if dur >= min_silence_s:
            durations.append(dur)
    return sorted(durations, reverse=True)


def expected_pauses_from_name(name: str) -> list[float]:
    pauses: list[float] = []
    for _, dur_s in PAUSE_RE.findall(name):
        pauses.append(float(dur_s))
    return pauses


def match_expected_pauses(found: list[float], expected: list[float], *, tolerance_s: float) -> bool:
    remaining = list(found)
    for exp in sorted(expected, reverse=True):
        best_idx = None
        best_diff = None
        for i, f in enumerate(remaining):
            diff = abs(f - exp)
            if diff <= tolerance_s and (best_diff is None or diff < best_diff):
                best_idx = i
                best_diff = diff
        if best_idx is None:
            return False
        remaining.pop(best_idx)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="QA for generated STT test audio suite")
    parser.add_argument("--dir", type=Path, required=True, help="Directory containing WAV files (recursive)")
    parser.add_argument("--rate", type=int, default=16000, help="Expected sample rate (default: 16000)")
    parser.add_argument("--threshold", type=int, default=50, help="Silence threshold abs(int16) (default: 50)")
    parser.add_argument("--min-silence", type=float, default=0.15, help="Minimum silence run duration seconds (default: 0.15)")
    parser.add_argument("--tolerance", type=float, default=0.10, help="Allowed pause duration error seconds (default: 0.10)")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of files checked (0=all)")
    args = parser.parse_args()

    if not args.dir.exists():
        print(f"❌ Not found: {args.dir}")
        return 2

    wavs = sorted(p for p in args.dir.rglob("*.wav") if p.is_file())
    if args.limit and args.limit > 0:
        wavs = wavs[: args.limit]

    if not wavs:
        print(f"❌ No WAV files under: {args.dir}")
        return 2

    failures = 0
    checked = 0

    for wav_path in wavs:
        checked += 1
        name = wav_path.name
        expected = expected_pauses_from_name(name)

        try:
            info, samples = read_wav_int16(wav_path)
            if info.rate != args.rate:
                raise ValueError(f"expected rate={args.rate}, got {info.rate}")

            found = silence_runs(samples, rate=info.rate, threshold=args.threshold, min_silence_s=args.min_silence)

            ok = True
            if expected:
                ok = match_expected_pauses(found, expected, tolerance_s=args.tolerance)

            if not ok:
                failures += 1
                print(f"❌ {wav_path}: expected pauses={expected} found silence runs={found[:5]}")
            else:
                print(f"✅ {wav_path}")

        except Exception as e:
            failures += 1
            print(f"❌ {wav_path}: {e}")

    print(f"\nChecked: {checked}  Failures: {failures}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
