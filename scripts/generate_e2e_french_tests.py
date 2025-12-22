#!/usr/bin/env python3
"""
Generate French E2E test audio using ElevenLabs.

Structure: "Alexa" + pause (0.3s) + command (segment-based like integration tests)
Validates: Wake word detection → STT → Intent classification
"""

import os
import sys
import subprocess
import tempfile
import json
import wave
from pathlib import Path
from elevenlabs import ElevenLabs
import config

# Music commands - 10 songs from playlist (simple French songs/artists that STT handles well)
# Format: (command_text, expected_intent, expected_params)
E2E_TESTS = [
    ("Je veux écouter maman", "play_music", {"query": "maman"}),
    ("Je veux écouter Louane", "play_music", {"query": "louane"}),
    ("Je veux écouter Stromae", "play_music", {"query": "stromae"}),
    ("Je veux écouter On écrit sur les murs", "play_music", {"query": "on écrit sur les murs"}),
    ("Je veux écouter Alors on danse", "play_music", {"query": "alors on danse"}),
    ("Tu peux jouer maman", "play_music", {"query": "maman"}),
    ("Tu peux jouer Louane", "play_music", {"query": "louane"}),
    ("Tu peux jouer Stromae", "play_music", {"query": "stromae"}),
    ("Tu peux mettre On écrit sur les murs", "play_music", {"query": "on écrit sur les murs"}),
    ("Tu peux mettre Alors on danse", "play_music", {"query": "alors on danse"}),
]

# Negative tests (no wake word - should NOT trigger)
NEGATIVE_TESTS = [
    ("Joue de la musique", None, {}),
    ("Tu peux mettre Frozen", None, {}),
    ("Mets Kids United", None, {}),
]

WAKE_PAUSE_S = 0.3  # Same as integration tests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
METADATA_PATH = PROJECT_ROOT / "tests" / "audio_samples" / "test_metadata.json"
SUITE_ID = "e2e_french"


def _wav_duration_s(path: Path) -> float:
    with wave.open(str(path), "rb") as wf:
        return wf.getnframes() / float(wf.getframerate())


def _load_metadata(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _default_usage_block() -> dict:
    return {
        "description": "Centralized test metadata for DRY test suites",
        "layout": {
            "suites": "Mapping of suite_id -> suite definition",
            "suites.<suite_id>.tests.positive": "List of positive test cases",
            "suites.<suite_id>.tests.negative": "List of negative test cases",
        },
        "fields": {
            "id": "Unique test identifier",
            "file": "Path to audio file (relative to repo root)",
            "full_phrase": "Complete phrase including wake word",
            "wake_word": "Wake word used (or null)",
            "command": "Command part only (without wake word)",
            "intent": "Expected intent classification",
            "parameters": "Expected intent parameters",
            "song_in_playlist": "Expected song file in playlist/ folder (optional)",
            "language": "Language code (fr/en)",
            "duration_s": "Total audio duration in seconds (optional)",
            "wake_word_end_s": "When wake word ends (seconds from start)",
            "pause_end_s": "When pause ends (seconds from start)",
            "command_start_s": "When command starts (seconds from start)",
            "command_duration_s": "Duration of command part only (optional)",
        },
    }


def _generate_tts_segment(client: ElevenLabs, text: str, voice_id: str) -> bytes:
    """Generate TTS audio and convert to 16kHz mono WAV."""
    with tempfile.TemporaryDirectory() as tmpdir:
        mp3_path = Path(tmpdir) / "tts.mp3"
        wav_path = Path(tmpdir) / "tts.wav"

        # Generate audio with ElevenLabs
        audio = client.text_to_speech.convert(
            voice_id=voice_id,
            text=text,
            model_id="eleven_multilingual_v2"
        )

        # Save as MP3
        audio_bytes = b"".join(audio)
        with open(mp3_path, "wb") as f:
            f.write(audio_bytes)

        # Convert to 16kHz mono WAV
        subprocess.run([
            'ffmpeg', '-y', '-i', str(mp3_path),
            '-ar', '16000', '-ac', '1',
            str(wav_path)
        ], check=True, capture_output=True)

        return wav_path.read_bytes()


def _create_silence(duration_s: float) -> bytes:
    """Create silence segment using sox."""
    with tempfile.TemporaryDirectory() as tmpdir:
        wav_path = Path(tmpdir) / "silence.wav"
        subprocess.run([
            'sox', '-n', '-r', '16000', '-c', '1', '-b', '16',
            '-e', 'signed-integer', str(wav_path),
            'trim', '0.0', f'{duration_s:.3f}'
        ], check=True, capture_output=True)
        return wav_path.read_bytes()


def _concatenate_segments(segments: list[bytes], output_path: Path):
    """Concatenate audio segments using sox."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Write each segment to temp file
        segment_files = []
        for i, segment_data in enumerate(segments):
            seg_path = Path(tmpdir) / f"seg_{i}.wav"
            seg_path.write_bytes(segment_data)
            segment_files.append(str(seg_path))

        # Concatenate with sox
        output_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([
            'sox', *segment_files, str(output_path)
        ], check=True, capture_output=True)


def generate_test_audio(output_dir: Path):
    """Generate test audio files using ElevenLabs with segment-based approach."""

    # Get API key from env first, then config fallback
    api_key = os.getenv("ELEVENLABS_API_KEY") or getattr(config, "ELEVENLABS_API_KEY", None)
    if not api_key or api_key == "your_key_here":
        print("Error: ELEVENLABS_API_KEY not set in config.py")
        print("Or export it: export ELEVENLABS_API_KEY='your_key'")
        print("Add it to config.py: ELEVENLABS_API_KEY = 'your_key'")
        sys.exit(1)

    # Initialize client
    client = ElevenLabs(api_key=api_key)
    voice_id = "EXAVITQu4vr4xnSDxMaL"  # Sarah - French female voice

    # Create output directories
    positive_dir = output_dir / "positive"
    negative_dir = output_dir / "negative"
    positive_dir.mkdir(parents=True, exist_ok=True)
    negative_dir.mkdir(parents=True, exist_ok=True)

    # Generate "Alexa" wake word once (reusable)
    print("\n=== Generating wake word segment ===")
    wake_word_segment = _generate_tts_segment(client, "Alexa", voice_id)
    silence_segment = _create_silence(WAKE_PAUSE_S)

    # Calculate wake word duration for test reference
    import wave
    with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
        tmp.write(wake_word_segment)
        tmp.flush()
        with wave.open(tmp.name, 'rb') as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            wake_duration = frames / float(rate)

    skip_duration = wake_duration + WAKE_PAUSE_S
    print(f"✓ Wake word ({wake_duration:.2f}s) + pause ({WAKE_PAUSE_S}s) = {skip_duration:.2f}s")
    print(f"  → Tests should skip {skip_duration:.2f}s to extract command")

    # Generate positive tests (with Alexa)
    print("\n=== Generating Positive Tests (with wake word) ===")
    for i, (command_text, intent, params) in enumerate(E2E_TESTS, 1):
        filename = f"{i:02d}_{intent}.wav"
        filepath = positive_dir / filename

        print(f"\n{i}/{len(E2E_TESTS)}: Alexa [{WAKE_PAUSE_S}s] {command_text}")
        print(f"  Intent: {intent}")
        print(f"  File: {filename}")

        # Generate command segment
        command_segment = _generate_tts_segment(client, command_text, voice_id)

        # Concatenate: wake_word + silence + command
        _concatenate_segments([wake_word_segment, silence_segment, command_segment], filepath)

        print(f"  ✓ Saved (16kHz WAV)")

    # Generate negative tests (without Alexa)
    print("\n\n=== Generating Negative Tests (no wake word) ===")
    for i, (command_text, intent, params) in enumerate(NEGATIVE_TESTS, 1):
        filename = f"{i:02d}_no_wake_word.wav"
        filepath = negative_dir / filename

        print(f"\n{i}/{len(NEGATIVE_TESTS)}: {command_text}")
        print(f"  Should NOT trigger")
        print(f"  File: {filename}")

        # Generate command only (no wake word)
        command_segment = _generate_tts_segment(client, command_text, voice_id)

        # Write directly
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_wav = Path(tmpdir) / "temp.wav"
            temp_wav.write_bytes(command_segment)
            subprocess.run(['cp', str(temp_wav), str(filepath)], check=True)

        print(f"  ✓ Saved (16kHz WAV)")

    # Create manifest
    manifest_path = output_dir / "manifest.json"
    manifest = {
        "metadata": {
            "wake_word_duration_s": wake_duration,
            "pause_duration_s": WAKE_PAUSE_S,
            "command_skip_s": skip_duration,
            "voice": "Sarah (ElevenLabs)",
            "voice_id": voice_id,
            "structure": "segment-based"
        },
        "positive_tests": [
            {
                "id": i,
                "phrase": f"Alexa. {command_text}",  # Full phrase with wake word
                "command": command_text,  # Command only
                "intent": intent,
                "params": params,
                "file": f"positive/{i:02d}_{intent}.wav",
                "structure": f"alexa + {WAKE_PAUSE_S}s + command"
            }
            for i, (command_text, intent, params) in enumerate(E2E_TESTS, 1)
        ],
        "negative_tests": [
            {
                "id": i,
                "phrase": command_text,
                "intent": None,
                "file": f"negative/{i:02d}_no_wake_word.wav"
            }
            for i, (command_text, intent, params) in enumerate(NEGATIVE_TESTS, 1)
        ]
    }

    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    # Update centralized metadata (tracked) for DRY test suites
    metadata = _load_metadata(METADATA_PATH)
    metadata["version"] = "3.0"
    if not isinstance(metadata.get("suites"), dict):
        metadata["suites"] = {}
    if "usage" not in metadata:
        metadata["usage"] = _default_usage_block()

    existing_suite = metadata["suites"].get(SUITE_ID, {})
    existing_positive_by_id = {
        int(t.get("id")): t for t in existing_suite.get("tests", {}).get("positive", []) if "id" in t
    }

    def _build_positive_case(i: int, command_text: str, intent: str, params: dict) -> dict:
        rel_file = f"tests/audio_samples/e2e_french/positive/{i:02d}_{intent}.wav"
        wav_path = PROJECT_ROOT / rel_file
        total_s = _wav_duration_s(wav_path) if wav_path.exists() else None
        duration_s = round(total_s, 2) if total_s is not None else None
        wake_word_end_s = round(wake_duration, 2)
        pause_end_s = round(wake_duration + WAKE_PAUSE_S, 2)
        command_start_s = pause_end_s
        command_duration_s = round(max(0.0, (duration_s or 0.0) - command_start_s), 2) if duration_s else None

        base = {
            "id": i,
            "file": rel_file,
            "full_phrase": f"Alexa. {command_text}",
            "wake_word": "Alexa",
            "command": command_text,
            "intent": intent,
            "parameters": params,
            "language": "fr",
            "duration_s": duration_s,
            "wake_word_end_s": wake_word_end_s,
            "pause_end_s": pause_end_s,
            "command_start_s": command_start_s,
            "command_duration_s": command_duration_s,
        }

        existing = existing_positive_by_id.get(i, {})
        if "song_in_playlist" in existing:
            base["song_in_playlist"] = existing["song_in_playlist"]
        return base

    negative_existing_by_id = {
        int(t.get("id")): t for t in existing_suite.get("tests", {}).get("negative", []) if "id" in t
    }

    def _build_negative_case(i: int, command_text: str) -> dict:
        rel_file = f"tests/audio_samples/e2e_french/negative/{i:02d}_no_wake_word.wav"
        wav_path = PROJECT_ROOT / rel_file
        total_s = _wav_duration_s(wav_path) if wav_path.exists() else None
        duration_s = round(total_s, 2) if total_s is not None else None

        base = {
            "id": i,
            "file": rel_file,
            "full_phrase": command_text,
            "wake_word": None,
            "command": command_text,
            "intent": None,
            "parameters": {},
            "language": "fr",
            "should_trigger": False,
            "reason": "No wake word - should not activate",
            "duration_s": duration_s,
        }

        existing = negative_existing_by_id.get(i, {})
        for key in ("reason",):
            if key in existing:
                base[key] = existing[key]
        return base

    suite = {
        "generator": "scripts/generate_e2e_french_tests.py",
        "voice": {
            "provider": "ElevenLabs",
            "voice_id": voice_id,
            "voice_name": "Sarah",
            "language": "French",
            "model": "eleven_multilingual_v2",
        },
        "structure": {
            "type": "segment-based",
            "wake_word": "Alexa",
            "wake_word_duration_s": wake_duration,
            "pause_duration_s": WAKE_PAUSE_S,
            "command_start_s": skip_duration,
            "description": "Wake word + 0.3s pause + command",
        },
        "audio_format": {
            "format": "WAV",
            "sample_rate": 16000,
            "channels": 1,
            "bit_depth": 16,
            "encoding": "PCM signed integer",
        },
        "tests": {
            "positive": [
                _build_positive_case(i, command_text, intent, params)
                for i, (command_text, intent, params) in enumerate(E2E_TESTS, 1)
            ],
            "negative": [
                _build_negative_case(i, command_text)
                for i, (command_text, _, __) in enumerate(NEGATIVE_TESTS, 1)
            ],
        },
    }

    metadata["suites"][SUITE_ID] = suite

    with open(METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"\n\n✓ Manifest: {manifest_path}")
    print(f"✓ Metadata:  {METADATA_PATH}")
    print(f"\n✓ Generated {len(E2E_TESTS)} positive + {len(NEGATIVE_TESTS)} negative tests")
    print(f"✓ Total: {len(E2E_TESTS) + len(NEGATIVE_TESTS)} files")
    print(f"\nStructure: Alexa + {WAKE_PAUSE_S}s pause + command (segment-based)")
    print(f"\nNext: pytest tests/test_e2e_french.py -v")

if __name__ == "__main__":
    output_dir = Path(__file__).parent.parent / "tests" / "audio_samples" / "e2e_french"
    print(f"Output directory: {output_dir}")
    generate_test_audio(output_dir)
