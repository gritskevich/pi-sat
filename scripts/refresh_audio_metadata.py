#!/usr/bin/env python3
"""
Refresh derived fields in tests/audio_samples/test_metadata.json.

Use-case:
- You add / edit test cases by hand (file + phrase + intent)
- This script fills in cheap derived metadata from the WAV:
  - duration_s
  - command_duration_s (when command_start_s is present)

KISS: no external deps (uses stdlib wave).
"""

from __future__ import annotations

import argparse
import json
import wave
from pathlib import Path


def wav_duration_s(path: Path) -> float:
    with wave.open(str(path), "rb") as wf:
        return wf.getnframes() / float(wf.getframerate())


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh derived audio metadata fields")
    parser.add_argument(
        "--path",
        type=Path,
        default=Path("tests/audio_samples/test_metadata.json"),
        help="Path to metadata JSON (default: tests/audio_samples/test_metadata.json)",
    )
    parser.add_argument("--suite", type=str, default="", help="Only refresh a single suite_id")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without writing")
    args = parser.parse_args()

    if not args.path.exists():
        raise SystemExit(f"Not found: {args.path}")

    repo_root = Path(__file__).resolve().parent.parent
    metadata = json.loads(args.path.read_text(encoding="utf-8"))
    suites = metadata.get("suites", {})
    if not isinstance(suites, dict):
        raise SystemExit("Invalid metadata: top-level 'suites' must be an object")

    updated = 0
    checked = 0

    for suite_id, suite in suites.items():
        if args.suite and suite_id != args.suite:
            continue

        tests = suite.get("tests", {})
        if not isinstance(tests, dict):
            continue

        for group_name in ("positive", "negative"):
            cases = tests.get(group_name, [])
            if not isinstance(cases, list):
                continue

            for case in cases:
                if not isinstance(case, dict):
                    continue

                file_rel = case.get("file")
                if not isinstance(file_rel, str) or not file_rel:
                    continue

                wav_path = repo_root / file_rel
                if not wav_path.exists():
                    continue

                checked += 1
                dur = round(wav_duration_s(wav_path), 2)
                if case.get("duration_s") != dur:
                    case["duration_s"] = dur
                    updated += 1

                command_start_s = case.get("command_start_s")
                if isinstance(command_start_s, (int, float)) and command_start_s >= 0:
                    cmd_dur = round(max(0.0, dur - float(command_start_s)), 2)
                    if case.get("command_duration_s") != cmd_dur:
                        case["command_duration_s"] = cmd_dur
                        updated += 1

    if args.dry_run:
        print(f"Checked WAV files: {checked}")
        print(f"Would update fields: {updated}")
        return 0

    args.path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Checked WAV files: {checked}")
    print(f"Updated fields: {updated}")
    print(f"Wrote: {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

