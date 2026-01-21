#!/usr/bin/env python3
import argparse
import json
import os

import config
from modules.intent_engine import IntentEngine
from modules.music_library import MusicLibrary
from modules.command_validator import CommandValidator


def load_phrases(log_path: str) -> list[str]:
    phrases = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = payload.get("text")
            if text:
                phrases.append(text)
    return phrases


def main() -> None:
    parser = argparse.ArgumentParser(description="One-shot intent + song match debug.")
    parser.add_argument(
        "--log",
        default=os.path.join(config.PROJECT_ROOT, "logs", "intent_log.jsonl"),
        help="Path to intent log (jsonl)."
    )
    parser.add_argument(
        "--phrase",
        action="append",
        default=[],
        help="Phrase to test (repeatable)."
    )
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="Top-N song matches to display."
    )
    args = parser.parse_args()

    phrases = list(args.phrase)
    if not phrases:
        phrases = load_phrases(args.log)

    engine = IntentEngine(
        fuzzy_threshold=getattr(config, "FUZZY_MATCH_THRESHOLD", 50),
        language=getattr(config, "LANGUAGE", "fr"),
        debug=False,
    )

    library = MusicLibrary(
        library_path=getattr(config, "MUSIC_LIBRARY", None),
        fuzzy_threshold=getattr(config, "FUZZY_MATCH_THRESHOLD", 50),
        phonetic_enabled=True,
        phonetic_weight=getattr(config, "PHONETIC_WEIGHT", 0.6),
        debug=False,
    )
    library.load_from_filesystem()
    validator = CommandValidator(music_library=library, language=getattr(config, "LANGUAGE", "fr"), debug=False)

    for idx, text in enumerate(phrases, 1):
        intent = engine.classify(text)
        print(f"\n[{idx}] STT: {text!r}")
        if not intent:
            print("  intent: None")
            continue
        print(f"  intent: {intent.intent_type} (confidence={intent.confidence:.2f})")
        validation = validator.validate(intent)
        if intent.intent_type == "play_music":
            query_sent = None
            if validation.validated_params and validation.validated_params.get("query"):
                query_sent = validation.validated_params.get("query")
            elif intent.parameters.get("query"):
                query_sent = intent.parameters.get("query")
            print(f"  song_query: {query_sent!r}")
            print(f"  validation: {validation.is_valid} (confidence={validation.confidence:.2f})")
            if query_sent:
                topn = library.rank_matches(query_sent, limit=args.top)
                print("  top_matches:")
                for path, score in topn:
                    print(f"    - {path} ({score:.2f})")
        else:
            print(f"  validation: {validation.is_valid} (confidence={validation.confidence:.2f})")


if __name__ == "__main__":
    main()
