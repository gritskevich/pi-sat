#!/usr/bin/env python3
"""
Generate French STT test audio using ElevenLabs (kid girl voice).

PoC/KISS: uses existing 117 French "full" test phrases and writes a parallel
ElevenLabs-generated suite for comparison.

Output:
  tests/audio_samples/language_tests/french_full_elevenlabs/

Requires:
  pip install elevenlabs
  sudo apt install -y sox
"""

import json
import os
import sys
import tempfile
import subprocess
import shutil
from pathlib import Path
from typing import Dict
from urllib import request

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.generate_language_test_audio import FRENCH_FULL_PHRASES
import config


API_URL = "https://api.elevenlabs.io/v1/text-to-speech"
DEFAULT_MODEL = "eleven_multilingual_v2"
DEFAULT_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID")
DEFAULT_VOICE_NAME = os.getenv("ELEVENLABS_VOICE_NAME")


EXTRA_FRENCH_FULL_PHRASES = {}


def _load_api_key() -> str:
    key = os.getenv("ELEVENLABS_API_KEY")
    if key:
        return key
    key = getattr(config, "ELEVENLABS_API_KEY", None)
    if key:
        return key
    config_path = Path("config.sh")
    if config_path.exists():
        for line in config_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line.replace("export ", "", 1).strip()
            if "ELEVENLABS_API_KEY" in line:
                _, _, value = line.partition("=")
                value = value.strip().strip('"').strip("'")
                if value:
                    return value
    raise RuntimeError("ELEVENLABS_API_KEY not found in env or config.sh")


def _ensure_sox() -> None:
    if not shutil.which("sox"):
        raise RuntimeError("Missing dependency: sox (install with: sudo apt install -y sox)")


def _load_expected_phrases() -> Dict[str, str]:
    expected_path = Path("tests/audio_samples/language_tests/french_full/expected_intents.json")
    data = json.loads(expected_path.read_text(encoding="utf-8"))
    phrase_map = {f"{name}.wav": text for name, text in FRENCH_FULL_PHRASES}
    phrase_map.update(EXTRA_FRENCH_FULL_PHRASES)

    missing = sorted(set(data.keys()) - set(phrase_map.keys()))
    if missing:
        raise RuntimeError(f"Missing phrases for: {missing}")
    return {name: phrase_map[name] for name in data.keys()}


def _resolve_voice_id(api_key: str, voice_id: str | None, voice_name: str | None) -> tuple[str, str]:
    if voice_id:
        return voice_id, "custom"

    req = request.Request(
        "https://api.elevenlabs.io/v1/voices",
        headers={"xi-api-key": api_key},
        method="GET",
    )
    with request.urlopen(req, timeout=20) as response:
        data = json.loads(response.read().decode("utf-8"))

    voices = data.get("voices", [])
    if not voices:
        raise RuntimeError("No voices returned from ElevenLabs API")

    if voice_name:
        for voice in voices:
            name = voice.get("name", "")
            if name.lower() == voice_name.lower():
                return voice.get("voice_id"), name
        raise RuntimeError(f"Voice name not found: {voice_name}")

    def score_voice(voice: dict) -> int:
        labels = voice.get("labels", {})
        description = (voice.get("description") or "").lower()
        name = (voice.get("name") or "").lower()
        score = 0
        if labels.get("gender") == "female":
            score += 3
        if labels.get("age") in {"young", "child"}:
            score += 2
        if labels.get("language") == "fr":
            score += 1
        if labels.get("descriptive") in {"cute", "playful"}:
            score += 1
        if any(token in description for token in ("child", "kid", "girl")):
            score += 1
        if any(token in name for token in ("girl", "kid", "child")):
            score += 1
        return score

    scored = [(score_voice(voice), voice) for voice in voices]
    scored.sort(key=lambda item: item[0], reverse=True)
    best = scored[0][1]
    return best.get("voice_id"), best.get("name", "unknown")


def _elevenlabs_tts(text: str, api_key: str, voice_id: str, model_id: str, out_mp3: Path) -> None:
    try:
        from elevenlabs.client import ElevenLabs
    except ModuleNotFoundError as exc:
        raise RuntimeError("Missing elevenlabs package. Install with: pip install elevenlabs") from exc

    client = ElevenLabs(api_key=api_key)
    audio_iter = client.text_to_speech.convert(
        voice_id,
        text=text,
        model_id=model_id,
    )
    with out_mp3.open("wb") as handle:
        for chunk in audio_iter:
            handle.write(chunk)


def _mp3_to_wav_16k(in_mp3: Path, out_wav: Path) -> None:
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["sox", str(in_mp3), "-r", "16000", "-c", "1", str(out_wav)],
        check=True,
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Generate French test audio via ElevenLabs")
    parser.add_argument("--voice-id", default=DEFAULT_VOICE_ID, help="ElevenLabs voice ID")
    parser.add_argument("--voice-name", default=DEFAULT_VOICE_NAME, help="ElevenLabs voice name")
    parser.add_argument("--model-id", default=DEFAULT_MODEL, help="ElevenLabs model ID")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("tests/audio_samples/language_tests/french_full_elevenlabs"),
        help="Output directory",
    )
    parser.add_argument("--limit", type=int, default=0, help="Limit number of files (0 = all)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    api_key = _load_api_key()
    _ensure_sox()
    voice_id, voice_name = _resolve_voice_id(api_key, args.voice_id, args.voice_name)

    phrases = _load_expected_phrases()
    items = list(phrases.items())
    if args.limit > 0:
        items = items[: args.limit]

    args.output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("ElevenLabs French Test Audio Generator")
    print("=" * 60)
    print(f"Output: {args.output_dir}")
    print(f"Voice: {voice_name} ({voice_id})")
    print(f"Model ID: {args.model_id}")
    print(f"Files: {len(items)}")

    for idx, (filename, text) in enumerate(items, 1):
        if args.verbose:
            print(f"[{idx}/{len(items)}] {filename}: {text}")
        with tempfile.TemporaryDirectory() as tmpdir:
            mp3_path = Path(tmpdir) / "tts.mp3"
            _elevenlabs_tts(text, api_key, voice_id, args.model_id, mp3_path)
            _mp3_to_wav_16k(mp3_path, args.output_dir / filename)

    print("\n✅ ElevenLabs suite generated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
