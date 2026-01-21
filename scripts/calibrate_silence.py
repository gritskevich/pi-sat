#!/usr/bin/env python3
import argparse

from modules.speech_recorder import SpeechRecorder


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate ambient RMS for adaptive silence.")
    parser.add_argument("--seconds", type=float, default=3.0, help="Duration to sample ambient noise.")
    args = parser.parse_args()

    print("Stay quiet. Sampling ambient noise...")
    recorder = SpeechRecorder(debug=False)
    ambient = recorder.calibrate_ambient(seconds=args.seconds)
    suggested_min = max(300.0, ambient * 1.2)

    print(f"Ambient RMS: {ambient:.1f}")
    print("Suggested config:")
    print(f"  export ADAPTIVE_MIN_SILENCE_RMS={suggested_min:.1f}")


if __name__ == "__main__":
    main()
