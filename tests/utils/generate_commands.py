"""
Synthetic Voice Command Generator

Generates realistic voice command audio files using Piper TTS.
Creates test data for Intent Engine and E2E testing.
"""

import os
import sys
import subprocess
from pathlib import Path



# Voice commands to generate
VOICE_COMMANDS = {
    'music_control': [
        "Play maman",
        "Play Kids United",
        "Play Grace Kelly",
        "Play my favorites",
        "Pause",
        "Stop",
        "Skip",
        "Next song",
        "Previous",
        "Go back",
        "Resume",
    ],
    'volume_control': [
        "Louder",
        "Volume up",
        "Increase volume",
        "Quieter",
        "Volume down",
        "Decrease volume",
        "Lower the volume",
    ],
    'favorites': [
        "I love this",
        "I love this song",
        "Like this",
        "Like this song",
        "Add to favorites",
        "Favorite this",
        "Save this song",
    ],
    'sleep_timer': [
        "Stop in 30 minutes",
        "Stop in 15 minutes",
        "Stop in 60 minutes",
        "Sleep timer 30 minutes",
        "Turn off in 30 minutes",
    ],
    'fuzzy_matching': [
        # Intentional typos for fuzzy matching tests
        "Play mamann",  # Typo in "maman"
        "Play kids united",  # Missing "the"
        "Play favorits",  # Typo in "favorites"
        "Play grace kely",  # Typo in "Kelly"
        "Pley maman",  # Typo in "Play"
    ],
    'edge_cases': [
        "Play",  # No song name
        "Ummm play maman",  # Filler words
        "Could you play maman please",  # Polite phrasing
        "Play play play",  # Repetition
        "",  # Empty (will skip)
    ],
}


def generate_command_wav(text, output_path, voice_model=None):
    """
    Generate WAV file from text using Piper TTS.

    Args:
        text: Text to convert to speech
        output_path: Path to save WAV file
        voice_model: Optional voice model path

    Returns:
        bool: True if successful
    """
    if not text or not text.strip():
        print(f"  ⊗ Skipping empty text")
        return False

    if voice_model is None:
        voice_model = project_root / 'resources' / 'voices' / 'en_US-lessac-medium.onnx'

    if not voice_model.exists():
        print(f"  ✗ Voice model not found: {voice_model}")
        return False

    try:
        # Generate raw PCM audio with Piper, then convert to WAV with sox
        # Use shell piping for simplicity
        cmd = f'''echo {subprocess.list2cmdline([text])} | \
/usr/local/bin/piper --model {subprocess.list2cmdline([str(voice_model)])} --output-raw | \
sox -r 22050 -e signed-integer -b 16 -c 1 -t raw - {subprocess.list2cmdline([output_path])}'''

        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            check=True,
            timeout=30
        )

        # Verify file was created
        if Path(output_path).exists() and Path(output_path).stat().st_size > 0:
            return True
        else:
            return False

    except subprocess.TimeoutExpired:
        print(f"  ✗ Timeout generating audio")
        return False
    except subprocess.CalledProcessError as e:
        print(f"  ✗ Error generating audio: {e.stderr if e.stderr else e}")
        return False
    except Exception as e:
        print(f"  ✗ Unexpected error: {e}")
        return False


def generate_all_commands(output_dir=None, voice_model=None, commands_dict=None):
    """
    Generate all voice command WAV files.

    Args:
        output_dir: Directory to save WAV files (default: tests/audio_samples/synthetic/)
        voice_model: Optional voice model path
        commands_dict: Optional dict of commands to generate (default: VOICE_COMMANDS)

    Returns:
        dict: Results per category
    """
    if commands_dict is None:
        commands_dict = VOICE_COMMANDS

    if output_dir is None:
        output_dir = project_root / 'tests' / 'audio_samples' / 'synthetic'

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating synthetic voice commands...")
    print(f"Output directory: {output_dir}")
    print()

    results = {}
    total_generated = 0
    total_failed = 0

    for category, commands in commands_dict.items():
        print(f"[{category.upper().replace('_', ' ')}]")

        category_dir = output_dir / category
        category_dir.mkdir(exist_ok=True)

        generated = 0
        failed = 0

        for i, command in enumerate(commands, 1):
            if not command.strip():
                continue

            # Create safe filename
            safe_filename = command.lower()
            safe_filename = safe_filename.replace(" ", "_")
            safe_filename = safe_filename.replace("'", "")
            safe_filename = ''.join(c for c in safe_filename if c.isalnum() or c == '_')
            filename = f"{i:02d}_{safe_filename}.wav"

            output_path = category_dir / filename

            print(f"  Generating: '{command}'")

            success = generate_command_wav(command, str(output_path), voice_model)

            if success:
                size_kb = output_path.stat().st_size / 1024
                print(f"    ✓ Saved: {filename} ({size_kb:.1f} KB)")
                generated += 1
            else:
                print(f"    ✗ Failed: {filename}")
                failed += 1

        results[category] = {'generated': generated, 'failed': failed}
        total_generated += generated
        total_failed += failed

        print()

    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)

    for category, counts in results.items():
        print(f"{category:20s}: {counts['generated']:3d} generated, {counts['failed']:3d} failed")

    print("-" * 60)
    print(f"{'TOTAL':20s}: {total_generated:3d} generated, {total_failed:3d} failed")
    print("=" * 60)

    return results


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Generate synthetic voice commands')
    parser.add_argument(
        '--output-dir',
        default=None,
        help='Output directory (default: tests/audio_samples/synthetic/)'
    )
    parser.add_argument(
        '--voice-model',
        default=None,
        help='Voice model path (default: resources/voices/en_US-lessac-medium.onnx)'
    )
    parser.add_argument(
        '--category',
        choices=list(VOICE_COMMANDS.keys()),
        help='Generate only specific category'
    )

    args = parser.parse_args()

    # Filter commands if category specified
    commands_to_generate = VOICE_COMMANDS
    if args.category:
        commands_to_generate = {args.category: VOICE_COMMANDS[args.category]}

    results = generate_all_commands(
        output_dir=args.output_dir,
        voice_model=args.voice_model,
        commands_dict=commands_to_generate
    )

    # Check if all succeeded
    total_failed = sum(r['failed'] for r in results.values())

    if total_failed == 0:
        print("\n✓ All commands generated successfully!")
        sys.exit(0)
    else:
        print(f"\n✗ {total_failed} commands failed to generate")
        sys.exit(1)


if __name__ == '__main__':
    main()
