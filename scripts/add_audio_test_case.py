#!/usr/bin/env python3
"""
Add/mark a WAV file in tests/audio_samples/test_metadata.json.

Goal: make it easy to register hand-made/generated files (e.g. "ratrapper") with full metadata,
so pytest suites can stay DRY and data-driven.

French-first defaults:
- language=fr
- wake_word=Alexa (for positive cases unless overridden)
"""

from __future__ import annotations

import argparse
import json
import wave
from pathlib import Path


def wav_duration_s(path: Path) -> float:
    with wave.open(str(path), "rb") as wf:
        return wf.getnframes() / float(wf.getframerate())


def repo_relpath(repo_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except Exception:
        return str(path)


def load_json(path: Path) -> dict:
    if not path.exists():
        return {"version": "3.0", "suites": {}, "usage": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Add a test case to audio metadata registry")
    parser.add_argument("--metadata", type=Path, default=Path("tests/audio_samples/test_metadata.json"))
    parser.add_argument("--suite", type=str, required=True, help="Suite id (e.g. e2e_french)")
    parser.add_argument("--group", type=str, choices=("positive", "negative"), required=True)
    parser.add_argument("--file", type=Path, required=True, help="WAV path (absolute or repo-relative)")
    parser.add_argument("--id", type=int, default=0, help="Optional explicit id (default: auto)")
    parser.add_argument("--language", type=str, default="fr")
    parser.add_argument("--wake-word", type=str, default="", help="Wake word text (empty => auto)")
    parser.add_argument("--full-phrase", type=str, required=True)
    parser.add_argument("--command", type=str, required=True)
    parser.add_argument("--intent", type=str, default="", help="Expected intent (empty => null for negative)")
    parser.add_argument("--parameters", type=str, default="{}", help="JSON object string (default: {})")
    parser.add_argument("--song-in-playlist", type=str, default="")
    parser.add_argument("--wake-word-end-s", type=float, default=-1.0)
    parser.add_argument("--pause-end-s", type=float, default=-1.0)
    parser.add_argument("--command-start-s", type=float, default=-1.0)
    parser.add_argument("--reason", type=str, default="", help="For negative tests: why it should not trigger")
    parser.add_argument("--dry-run", action="store_true", help="Print the case JSON without writing")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    wav_path = (repo_root / args.file).resolve() if not args.file.is_absolute() else args.file.resolve()
    if not wav_path.exists():
        raise SystemExit(f"Not found: {wav_path}")

    duration_s = round(wav_duration_s(wav_path), 2)

    metadata = load_json(args.metadata)
    metadata["version"] = "3.0"
    if not isinstance(metadata.get("suites"), dict):
        metadata["suites"] = {}

    suite = metadata["suites"].setdefault(
        args.suite,
        {
            "generator": "",
            "voice": {},
            "structure": {},
            "audio_format": {},
            "tests": {"positive": [], "negative": []},
        },
    )
    suite.setdefault("tests", {"positive": [], "negative": []})
    suite["tests"].setdefault("positive", [])
    suite["tests"].setdefault("negative", [])

    group_cases = suite["tests"][args.group]
    next_id = (max((int(c.get("id", 0)) for c in group_cases if isinstance(c, dict)), default=0) + 1)
    case_id = args.id if args.id > 0 else next_id

    try:
        parameters = json.loads(args.parameters)
    except Exception as e:
        raise SystemExit(f"Invalid --parameters JSON: {e}")
    if not isinstance(parameters, dict):
        raise SystemExit("--parameters must be a JSON object")

    if args.group == "positive":
        wake_word = args.wake_word if args.wake_word else "Alexa"
        intent = args.intent or "play_music"
    else:
        wake_word = args.wake_word if args.wake_word else None
        intent = args.intent or None

    case: dict = {
        "id": case_id,
        "file": repo_relpath(repo_root, wav_path),
        "full_phrase": args.full_phrase,
        "wake_word": wake_word,
        "command": args.command,
        "intent": intent,
        "parameters": parameters,
        "language": args.language,
        "duration_s": duration_s,
    }

    if args.song_in_playlist:
        case["song_in_playlist"] = args.song_in_playlist

    if args.wake_word_end_s >= 0:
        case["wake_word_end_s"] = round(args.wake_word_end_s, 2)
    if args.pause_end_s >= 0:
        case["pause_end_s"] = round(args.pause_end_s, 2)
    if args.command_start_s >= 0:
        case["command_start_s"] = round(args.command_start_s, 2)
        case["command_duration_s"] = round(max(0.0, duration_s - float(case["command_start_s"])), 2)

    if args.group == "negative":
        case["should_trigger"] = False
        if args.reason:
            case["reason"] = args.reason

    if args.dry_run:
        print(json.dumps(case, indent=2, ensure_ascii=False))
        return 0

    # Upsert: replace existing id if present, else append.
    replaced = False
    for idx, existing in enumerate(group_cases):
        if isinstance(existing, dict) and existing.get("id") == case_id:
            group_cases[idx] = case
            replaced = True
            break
    if not replaced:
        group_cases.append(case)

    args.metadata.parent.mkdir(parents=True, exist_ok=True)
    args.metadata.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    action = "Replaced" if replaced else "Added"
    print(f"{action} {args.suite}/{args.group} id={case_id}: {case['file']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

