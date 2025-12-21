#!/usr/bin/env python3
"""
Generate comprehensive music control test audio suite for STT testing.

This script generates realistic test audio files using Piper TTS for:
- French (default) and English music control commands
- Wake word ("Alexa") variations (with/without, with different pause durations)
- Realistic command patterns from Intent Engine
- Precise pause control by stitching generated segments (Piper does not support SSML breaks)

Output structure:
  tests/audio_samples/integration/
    fr/  # French commands
      alexa_pause_0.3s_tu_peux_jouer_maman.wav
      mid_pause_0.5s_tu_peux_jouer_maman.wav
      alexa_pause_0.3s_mid_pause_0.5s_tu_peux_jouer_maman.wav
      tu_peux_jouer_maman.wav  # No wake word, no mid-pause
      ...
    en/  # English commands
      alexa_pause_0.3s_play_maman.wav
      ...
"""

import sys
import subprocess
import hashlib
import shutil
import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import Iterable, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import config

# ============================================================================
# TEST COMMAND PHRASES (aligned with Intent Engine triggers)
# ============================================================================

@dataclass(frozen=True)
class CommandSpec:
    command_id: str
    text: str
    mid_split: Optional[tuple[str, str]] = None


FR_COMMANDS: list[CommandSpec] = [
    CommandSpec("tu_peux_jouer_maman", "Tu peux jouer maman", mid_split=("Tu peux jouer", "maman")),
    CommandSpec("tu_peux_mettre_louane", "Tu peux mettre Louane", mid_split=("Tu peux mettre", "Louane")),
    CommandSpec("je_veux_ecouter_kids_united", "Je veux écouter Kids United", mid_split=("Je veux écouter", "Kids United")),
    CommandSpec("tu_peux_jouer_grace_kelly", "Tu peux jouer Grace Kelly", mid_split=("Tu peux jouer", "Grace Kelly")),
    CommandSpec("tu_peux_mettre_alors_on_danse", "Tu peux mettre Alors on danse", mid_split=("Tu peux mettre", "Alors on danse")),
    CommandSpec("pause", "Pause"),
    CommandSpec("reprends", "Reprends"),
    CommandSpec("arrete", "Arrête"),
    CommandSpec("suivant", "Suivant"),
    CommandSpec("precedent", "Précédent"),
    CommandSpec("plus_fort", "Plus fort"),
    CommandSpec("moins_fort", "Moins fort"),
    CommandSpec("jadore_ca", "J'adore ça"),
    CommandSpec("ajoute_aux_favoris", "Ajoute aux favoris", mid_split=("Ajoute", "aux favoris")),
    CommandSpec("repete_cette_chanson", "Répète cette chanson", mid_split=("Répète", "cette chanson")),
    CommandSpec("melange", "Mélange"),
    CommandSpec("arrete_dans_30_minutes", "Arrête dans 30 minutes", mid_split=("Arrête", "dans 30 minutes")),
    CommandSpec("joue_mes_favoris", "Joue mes favoris", mid_split=("Joue", "mes favoris")),
    CommandSpec("joue_maman_ensuite", "Joue maman ensuite", mid_split=("Joue maman", "ensuite")),
    CommandSpec("ajoute_maman", "Ajoute maman", mid_split=("Ajoute", "maman")),
]

EN_COMMANDS: list[CommandSpec] = [
    CommandSpec("play_maman", "Play maman", mid_split=("Play", "maman")),
    CommandSpec("play_kids_united", "Play Kids United", mid_split=("Play", "Kids United")),
    CommandSpec("play_magic_system", "Play Magic System", mid_split=("Play", "Magic System")),
    CommandSpec("pause", "Pause"),
    CommandSpec("resume", "Resume"),
    CommandSpec("stop", "Stop"),
    CommandSpec("next", "Next"),
    CommandSpec("previous", "Previous"),
    CommandSpec("louder", "Louder"),
    CommandSpec("quieter", "Quieter"),
    CommandSpec("i_love_this", "I love this"),
    CommandSpec("add_to_favorites", "Add to favorites", mid_split=("Add", "to favorites")),
    CommandSpec("repeat_this_song", "Repeat this song", mid_split=("Repeat", "this song")),
    CommandSpec("shuffle", "Shuffle"),
    CommandSpec("stop_in_30_minutes", "Stop in 30 minutes", mid_split=("Stop", "in 30 minutes")),
    CommandSpec("play_my_favorites", "Play my favorites", mid_split=("Play", "my favorites")),
]

def _run(cmd: list[str], *, timeout_s: int) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(cmd)}\n{result.stderr.strip()}")


def _hash_key(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()[:16]


def _piper_render(text: str, model_path: Path, out_wav_16k: Path, *, trim: bool = True) -> None:
    """
    Render text to a 16 kHz mono WAV using Piper + sox.

    Piper itself doesn't guarantee 16 kHz output; we resample with sox.
    """
    out_wav_16k.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_raw = Path(tmpdir) / "piper.wav"
        cmd = [
            str(config.PIPER_BINARY_PATH),
            "--model",
            str(model_path),
            "--output_file",
            str(tmp_raw),
            "--sentence_silence",
            "0.0",
        ]
        result = subprocess.run(cmd, input=text, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise RuntimeError(f"Piper failed ({result.returncode}) for text={text!r}\n{result.stderr.strip()}")
        if trim:
            _run(
                [
                    "sox",
                    str(tmp_raw),
                    "-r",
                    "16000",
                    "-c",
                    "1",
                    str(out_wav_16k),
                    "silence",
                    "1",
                    "0.05",
                    "0.1%",
                    "reverse",
                    "silence",
                    "1",
                    "0.05",
                    "0.1%",
                    "reverse",
                ],
                timeout_s=10,
            )
        else:
            _run(["sox", str(tmp_raw), "-r", "16000", "-c", "1", str(out_wav_16k)], timeout_s=10)


def _make_silence(duration_s: float, out_wav_16k: Path) -> None:
    out_wav_16k.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "sox",
            "-n",
            "-r",
            "16000",
            "-c",
            "1",
            "-b",
            "16",
            "-e",
            "signed-integer",
            str(out_wav_16k),
            "trim",
            "0.0",
            f"{duration_s:.3f}",
        ],
        timeout_s=5,
    )


def _concat(parts: list[Path], out_wav: Path) -> None:
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    _run(["sox", *[str(p) for p in parts], str(out_wav)], timeout_s=10)


# ============================================================================
# TEST SUITE GENERATION
# ============================================================================

@dataclass
class GenerationStats:
    generated: int = 0
    failed: int = 0


class SegmentCache:
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def tts(self, *, lang: str, text: str, model_path: Path) -> Path:
        key = _hash_key(lang, str(model_path), text)
        out = self.cache_dir / f"tts_{key}.wav"
        if not out.exists():
            _piper_render(text, model_path, out, trim=True)
        return out

    def silence(self, duration_s: float) -> Path:
        key = _hash_key("silence", f"{duration_s:.3f}")
        out = self.cache_dir / f"silence_{key}.wav"
        if not out.exists():
            _make_silence(duration_s, out)
        return out


def _format_pause_label(duration_s: float) -> str:
    return f"{duration_s:.1f}s" if (duration_s * 10).is_integer() else f"{duration_s:.2f}s"


def _assemble(
    *,
    cache: SegmentCache,
    lang: str,
    model_path: Path,
    wake_word: Optional[str],
    wake_pause_s: Optional[float],
    command: CommandSpec,
    mid_pause_s: Optional[float],
    out_wav: Path,
) -> None:
    parts: list[Path] = []

    if wake_word:
        parts.append(cache.tts(lang=lang, text=wake_word, model_path=model_path))
        if wake_pause_s and wake_pause_s > 0:
            parts.append(cache.silence(wake_pause_s))

    if mid_pause_s and command.mid_split:
        left, right = command.mid_split
        parts.append(cache.tts(lang=lang, text=left, model_path=model_path))
        if mid_pause_s > 0:
            parts.append(cache.silence(mid_pause_s))
        parts.append(cache.tts(lang=lang, text=right, model_path=model_path))
    else:
        parts.append(cache.tts(lang=lang, text=command.text, model_path=model_path))

    _concat(parts, out_wav)


def generate_language_suite(
    *,
    lang: str,
    commands: Iterable[CommandSpec],
    output_dir: Path,
    model_path: Path,
    cache_dir: Path,
    wake_word: str,
    wake_pauses_s: list[float],
    mid_pauses_s: list[float],
    verbose: bool,
) -> GenerationStats:
    output_dir.mkdir(parents=True, exist_ok=True)
    cache = SegmentCache(cache_dir)

    stats = GenerationStats()
    commands_list = list(commands)

    print(f"\n{'='*70}")
    print(f"Generating {lang.upper()} test suite ({len(commands_list)} commands)")
    print(f"{'='*70}")

    for idx, command in enumerate(commands_list, 1):
        if verbose:
            print(f"\n  [{idx}/{len(commands_list)}] {command.text}")

        variants: list[tuple[Optional[float], Optional[float], str]] = []
        variants.append((None, None, f"{command.command_id}.wav"))

        for wake_pause in wake_pauses_s:
            variants.append((wake_pause, None, f"alexa_pause_{_format_pause_label(wake_pause)}_{command.command_id}.wav"))

        if command.mid_split:
            for mid_pause in mid_pauses_s:
                variants.append((None, mid_pause, f"mid_pause_{_format_pause_label(mid_pause)}_{command.command_id}.wav"))
                for wake_pause in wake_pauses_s:
                    variants.append(
                        (
                            wake_pause,
                            mid_pause,
                            f"alexa_pause_{_format_pause_label(wake_pause)}_mid_pause_{_format_pause_label(mid_pause)}_{command.command_id}.wav",
                        )
                    )

        for wake_pause_s, mid_pause_s, filename in variants:
            try:
                out_wav = output_dir / filename
                _assemble(
                    cache=cache,
                    lang=lang,
                    model_path=model_path,
                    wake_word=wake_word if wake_pause_s is not None else None,
                    wake_pause_s=wake_pause_s,
                    command=command,
                    mid_pause_s=mid_pause_s,
                    out_wav=out_wav,
                )
                stats.generated += 1
            except Exception as e:
                stats.failed += 1
                print(f"  ❌ Failed: {filename}: {e}")

    return stats


def main():
    """Generate complete music test suite."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Generate music control test audio suite'
    )
    parser.add_argument(
        '--languages',
        nargs='+',
        choices=['fr', 'en', 'both'],
        default=['fr'],
        help='Languages to generate (default: fr)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=None,
        help='Output directory (default: tests/audio_samples/integration)'
    )
    parser.add_argument(
        '--clean',
        action='store_true',
        help='Delete language output dirs before generating'
    )
    parser.add_argument(
        '--wake-pauses',
        nargs='+',
        type=float,
        default=[0.0, 0.3, 0.8, 1.5],
        help='Silence durations (seconds) after wake word (default: 0 0.3 0.8 1.5)'
    )
    parser.add_argument(
        '--mid-pauses',
        nargs='+',
        type=float,
        default=[0.3, 0.8],
        help='Silence durations (seconds) to insert mid-phrase (default: 0.3 0.8)'
    )

    args = parser.parse_args()

    # Setup paths
    project_root = Path(__file__).parent.parent

    if args.output_dir:
        output_base = args.output_dir
    else:
        output_base = project_root / "tests" / "audio_samples" / "integration"

    # Voice models
    models = {
        'fr': Path(config.PIPER_MODEL_PATH_FR),
        'en': Path(config.PIPER_MODEL_PATH_EN),
    }

    # Determine which languages to generate
    if 'both' in args.languages:
        languages_to_generate = ['fr', 'en']
    else:
        languages_to_generate = args.languages

    # Validate models exist
    for lang in languages_to_generate:
        if not models[lang].exists():
            print(f"❌ Model not found: {models[lang]}")
            return 1

    print("=" * 70)
    print("Music Control Test Audio Generator")
    print("=" * 70)
    print(f"Output directory: {output_base}")
    print(f"Languages: {', '.join(languages_to_generate)}")
    print(f"Wake pauses: {args.wake_pauses}")
    print(f"Mid pauses: {args.mid_pauses}")

    # Generate test suites
    all_stats: dict[str, GenerationStats] = {}

    suites = {"fr": FR_COMMANDS, "en": EN_COMMANDS}

    for lang in languages_to_generate:
        out_dir = output_base / lang
        if args.clean and out_dir.exists():
            shutil.rmtree(out_dir)
        # Keep cache out of the generated suite directories to avoid polluting fixtures
        cache_dir = project_root / "tests" / "audio_samples" / "_cache_tts" / lang
        all_stats[lang] = generate_language_suite(
            lang=lang,
            commands=suites[lang],
            output_dir=out_dir,
            model_path=models[lang],
            cache_dir=cache_dir,
            wake_word="Alexa",
            wake_pauses_s=args.wake_pauses,
            mid_pauses_s=args.mid_pauses,
            verbose=args.verbose,
        )

    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    total_generated = 0
    total_failed = 0

    for lang, stats in all_stats.items():
        print(f"  {lang.upper()}:")
        print(f"    ✓ Generated: {stats.generated} files")
        if stats.failed > 0:
            print(f"    ✗ Failed: {stats.failed} files")

        total_generated += stats.generated
        total_failed += stats.failed

    print(f"\n  TOTAL: {total_generated} files generated")

    if total_failed > 0:
        print(f"  ⚠️  {total_failed} files failed")
        return 1

    print("\n✅ Test suite generation complete!")
    print("\nNext:")
    print(f"  `python scripts/qa_stt_audio_suite.py --dir {output_base / 'fr'}`")
    print(f"  `./pi-sat.sh benchmark_stt --engine hailo --lang fr --audio-dir {output_base / 'fr'} --runs 1 --files 10`")

    return 0


if __name__ == "__main__":
    sys.exit(main())
