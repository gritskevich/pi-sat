#!/usr/bin/env python3
"""
Regenerate French test audio with real playlist songs.

Fixes TTS pronunciation issues by:
1. Adding pause before "Joue" (emphasis)
2. Using "Mets" as alternative (better TTS pronunciation)
"""

import sys
import subprocess
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import config

# Real songs from playlist (kid-friendly)
SONGS = [
    ("maman", "maman"),  # Louane
    ("jour_1", "Jour 1"),  # Louane
    ("on_ecrit_sur_les_murs", "On écrit sur les murs"),  # Kids United
    ("le_lion_est_mort_ce_soir", "Le lion est mort ce soir"),  # Kids United
    ("alors_on_danse", "Alors on danse"),  # Stromae
    ("magic_in_the_air", "Magic in the Air"),  # Magic System
    ("grace_kelly", "Grace Kelly"),  # MIKA
    ("queen_of_kings", "Queen of Kings"),  # Alessandra
]

def generate_audio_with_pause(text: str, output_path: str, pause_duration: float = 0.3):
    """
    Generate TTS audio with pauses between words.

    Strategy: Use commas for natural pauses in TTS.
    Piper interprets commas as ~0.3s pause, periods as ~0.5s.
    """
    # Add commas between words for pause
    # "Joue Astronomia" → "Joue, , Astronomia" (double comma = longer pause)
    words = text.split()
    if len(words) > 1:
        # Insert double commas between command and song name
        text_with_pause = f"{words[0]}, , {' '.join(words[1:])}"
    else:
        text_with_pause = text

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(text_with_pause)
        f.flush()

        cmd = [
            config.PIPER_BINARY_PATH,
            '--model', config.PIPER_MODEL_PATH_FR,
            '--output_file', output_path
        ]

        with open(f.name, 'r') as input_file:
            result = subprocess.run(cmd, stdin=input_file, capture_output=True, text=True)

        Path(f.name).unlink()

        if result.returncode != 0:
            print(f"❌ TTS failed: {result.stderr}")
            return False

        return True

def generate_audio(text: str, output_path: str):
    """Generate TTS audio using Piper (backward compat wrapper)"""
    return generate_audio_with_pause(text, output_path)

def main():
    output_dir = Path("tests/audio_samples/language_tests/french_full")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("🔧 Generating test audio with real playlist songs...\n")

    generated = 0

    total = len(SONGS) * 2

    for song_id, song_name in SONGS:
        # Variant A: "Tu peux jouer" (more natural, better pronunciation)
        joue_text = f"Tu peux jouer {song_name}"
        joue_file = output_dir / f"tu_peux_jouer_{song_id}.wav"

        print(f"[{generated+1}/{total}] Generating: {joue_file.name}")
        print(f"  Text: '{joue_text}'")

        if generate_audio_with_pause(joue_text, str(joue_file)):
            print(f"  ✓ Generated")
        else:
            print(f"  ✗ Failed")
            continue

        generated += 1

        # Variant B: "Tu peux mettre" (alternative phrasing)
        mets_text = f"Tu peux mettre {song_name}"
        mets_file = output_dir / f"tu_peux_mettre_{song_id}.wav"

        print(f"[{generated+1}/{total}] Generating: {mets_file.name}")
        print(f"  Text: '{mets_text}'")

        if generate_audio_with_pause(mets_text, str(mets_file)):
            print(f"  ✓ Generated")
        else:
            print(f"  ✗ Failed")
            continue

        generated += 1

    print(f"\n✅ Generated {generated}/{total} audio files")
    print(f"\n📋 Next steps:")
    print(f"1. Update expected_intents.json with new files")
    print(f"2. Run: ./pi-sat.sh test_stt_intent")

if __name__ == '__main__':
    main()
