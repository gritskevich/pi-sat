#!/usr/bin/env python3
"""
Generate test audio files for French and English STT testing.

This script uses Piper TTS to generate realistic test audio files
that will be used to verify Hailo STT language detection.

Suites:
- French basic: 10 files (existing language detection fixtures)
- French full: 100+ files (kid-style command phrasing)
- English: 10 files (basic language detection fixtures)
"""

import sys
import subprocess
from pathlib import Path
import shutil

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import config

# Basic test phrases for French (10 files)
FRENCH_BASIC_PHRASES = [
    ("bonjour", "Bonjour, comment allez-vous?"),
    ("merci", "Merci beaucoup pour votre aide."),
    ("musique", "Joue de la musique s'il te plaît."),
    ("volume", "Monte le volume."),
    ("pause", "Mets en pause."),
    ("suivant", "Chanson suivante."),
    ("arrete", "Arrête la musique."),
    ("favoris", "Ajoute cette chanson aux favoris."),
    ("question", "Quelle heure est-il maintenant?"),
    ("belle_journee", "C'est une belle journée aujourd'hui."),
]

# Full test suite for French (kid-friendly phrasing)
FRENCH_MUSIC_LEADS = [
    ("tu_peux_jouer", "Tu peux jouer"),
    ("tu_peux_mettre", "Tu peux mettre"),
    ("je_veux_ecouter", "Je veux écouter"),
]

# Artists and songs pulled from the local playlist (9yo-friendly)
FRENCH_MUSIC_TERMS = [
    ("louane", "Louane"),
    ("kids_united", "Kids United"),
    ("mika", "MIKA"),
    ("stromae", "Stromae"),
    ("magic_system", "Magic System"),
    ("abba", "ABBA"),
    ("imagine_dragons", "Imagine Dragons"),
    ("monster_high", "Monster High"),
    ("maman", "maman"),
    ("jour_1", "Jour 1"),
    ("on_ecrit_sur_les_murs", "On écrit sur les murs"),
    ("le_lion_est_mort_ce_soir", "Le lion est mort ce soir"),
    ("grace_kelly", "Grace Kelly"),
    ("magic_in_the_air", "Magic in the Air"),
    ("alors_on_danse", "Alors on danse"),
    ("papaya", "Papaya"),
]

FRENCH_MUSIC_PHRASES = [
    (f"{lead_key}_{term_key}", f"{lead_text} {term_text}")
    for term_key, term_text in FRENCH_MUSIC_TERMS
    for lead_key, lead_text in FRENCH_MUSIC_LEADS
]

FRENCH_FULL_PHRASES = FRENCH_MUSIC_PHRASES + [
    ("joue_musique", "Joue de la musique"),
    ("mets_musique", "Mets de la musique"),
    ("lance_la_musique", "Lance la musique"),
    ("mets_une_chanson", "Mets une chanson"),
    ("joue_une_chanson", "Joue une chanson"),
    ("mets_des_chansons", "Mets des chansons"),
    ("joue_un_truc", "Joue un truc"),
    ("mets_musique_disney", "Mets de la musique Disney"),
    ("joue_musique_disney", "Joue de la musique Disney"),
    ("mets_musique_classique", "Mets de la musique classique"),
    ("joue_musique_classique", "Joue de la musique classique"),
    ("mets_musique_pour_danser", "Mets une musique pour danser"),
    ("pause_musique", "Pause la musique"),
    ("mets_pause", "Mets en pause"),
    ("stop_musique", "Arrête la musique"),
    ("arrete_tout", "Arrête tout"),
    ("reprends", "Reprends"),
    ("continue", "Continue"),
    ("suivant", "Chanson suivante"),
    ("passe_suivant", "Passe à la suivante"),
    ("precedent", "Chanson précédente"),
    ("reviens_en_arriere", "Reviens en arrière"),
    ("jadore_ca", "J'adore ça"),
    ("jaime_cette_chanson", "J'aime cette chanson"),
    ("mets_en_favori", "Mets en favori"),
    ("ajoute_aux_favoris", "Ajoute aux favoris"),
    ("garde_celle_la", "Garde celle-là"),
    ("joue_mes_favoris", "Joue mes favoris"),
    ("repete_cette_chanson", "Répète cette chanson"),
    ("encore", "Encore"),
    ("remets_la_meme", "Remets la même"),
    ("stop_repetition", "Arrête de répéter"),
    ("melange", "Mélange"),
    ("aleatoire", "Mets en aléatoire"),
    ("stop_melange", "Arrête le mélange"),
    ("joue_ensuite_maman", "Joue maman ensuite"),
    ("mets_apres_maman", "Mets maman après"),
    ("ajoute_file_maman", "Ajoute maman à la file"),
    ("plus_fort", "Plus fort"),
    ("monte_le_son", "Monte le son"),
    ("augmente_volume", "Augmente le volume"),
    ("moins_fort", "Moins fort"),
    ("baisse_le_son", "Baisse le son"),
    ("volume_plus_bas", "Mets le volume plus bas"),
    ("arrete_dans_10_minutes", "Arrête dans 10 minutes"),
    ("stop_dans_20_minutes", "Stop dans 20 minutes"),
    ("eteins_dans_5_minutes", "Éteins dans 5 minutes"),
    ("arrete_dans_une_demie_heure", "Arrête dans une demi-heure"),
    ("reveille_moi_a_7", "Réveille-moi à 7 heures"),
    ("mets_alarme_8", "Mets une alarme à 8 heures"),
    ("annule_alarme", "Annule l'alarme"),
    ("c_est_l_heure_du_dodo", "C'est l'heure du dodo ?"),
]

# Test phrases for English
ENGLISH_PHRASES = [
    ("hello", "Hello, how are you doing today?"),
    ("thanks", "Thank you very much for your help."),
    ("play_music", "Play some music please."),
    ("volume_up", "Turn the volume up."),
    ("pause", "Pause the music."),
    ("next", "Next song please."),
    ("stop", "Stop the music."),
    ("favorites", "Add this song to favorites."),
    ("question", "What time is it right now?"),
    ("nice_day", "It's a beautiful day today."),
]


def generate_audio(text, output_path, model_path, verbose=True):
    """Generate 16 kHz mono PCM WAV using Piper + sox (required by STT)."""
    if shutil.which("sox") is None:
        print("❌ Missing dependency: sox (install with: sudo apt install -y sox)")
        return False

    if verbose:
        print(f"  Generating: {output_path}")
        print(f"    Text: {text}")

    temp_path = Path(output_path).with_suffix(".tmp.wav")
    cmd = [config.PIPER_BINARY_PATH, '--model', model_path, '--output_file', str(temp_path), '--sentence_silence', '0.0']

    try:
        proc = subprocess.run(cmd, input=text, capture_output=True, text=True, timeout=20)
        if proc.returncode != 0:
            print(f"    ❌ Piper error: {proc.stderr.strip()}")
            return False

        res = subprocess.run(
            ['sox', str(temp_path), '-r', '16000', '-c', '1', output_path],
            capture_output=True,
            text=True,
            timeout=10
        )
        if res.returncode != 0:
            print(f"    ❌ Sox error: {res.stderr.strip()}")
            return False

        if verbose:
            file_size = Path(output_path).stat().st_size / 1024
            print(f"    ✓ Generated ({file_size:.1f} KB, 16kHz)")

        return True

    except subprocess.TimeoutExpired:
        print(f"    ❌ Timeout generating audio")
        return False
    except Exception as e:
        print(f"    ❌ Error: {e}")
        return False
    finally:
        temp_path.unlink(missing_ok=True)


def _resolve_suite_phrases(suite: str):
    if suite == "basic":
        return FRENCH_BASIC_PHRASES
    if suite == "full":
        return FRENCH_FULL_PHRASES
    return FRENCH_BASIC_PHRASES + FRENCH_FULL_PHRASES


def main():
    """Generate all test audio files."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate language test audio files")
    parser.add_argument(
        "--languages",
        nargs="+",
        choices=["fr", "en", "both"],
        default=["both"],
        help="Languages to generate (default: both)",
    )
    parser.add_argument(
        "--suite",
        choices=["basic", "full", "both"],
        default="basic",
        help="French suite to generate (default: basic)",
    )

    args = parser.parse_args()

    project_root = Path(__file__).parent.parent

    # Setup paths
    french_dir = project_root / "tests" / "audio_samples" / "language_tests" / "french"
    french_full_dir = project_root / "tests" / "audio_samples" / "language_tests" / "french_full"
    english_dir = project_root / "tests" / "audio_samples" / "language_tests" / "english"

    french_dir.mkdir(parents=True, exist_ok=True)
    french_full_dir.mkdir(parents=True, exist_ok=True)
    english_dir.mkdir(parents=True, exist_ok=True)

    # Voice models
    french_model = Path(config.PIPER_MODEL_PATH_FR)
    english_model = Path(config.PIPER_MODEL_PATH_EN)

    if not french_model.exists():
        print(f"❌ French model not found: {french_model}")
        return 1

    if not english_model.exists():
        print(f"❌ English model not found: {english_model}")
        return 1

    print("=" * 60)
    print("Generating Language Test Audio Files")
    print("=" * 60)

    # Determine which languages to generate
    if "both" in args.languages:
        languages_to_generate = ["fr", "en"]
    else:
        languages_to_generate = args.languages

    # Generate French audio
    french_phrases = _resolve_suite_phrases(args.suite)
    if args.suite in ("full", "both") and len(FRENCH_FULL_PHRASES) != 100:
        print(f"❌ Full French suite must contain 100 phrases, found {len(FRENCH_FULL_PHRASES)}")
        return 1

    basic_filenames = {name for name, _ in FRENCH_BASIC_PHRASES}

    if "fr" in languages_to_generate:
        if args.suite == "basic":
            french_target_dir = french_dir
        elif args.suite == "full":
            french_target_dir = french_full_dir
        else:
            french_target_dir = french_dir

        if args.suite == "basic":
            print(f"\n📢 Generating French basic test audio ({len(french_phrases)} files)...")
        elif args.suite == "full":
            print(f"\n📢 Generating French full test audio ({len(french_phrases)} files)...")
        else:
            print(f"\n📢 Generating French basic+full test audio ({len(french_phrases)} files)...")

    french_success = 0
    for filename, text in french_phrases:
        if args.suite == "both" and filename in basic_filenames:
            output_path = french_dir / f"{filename}.wav"
        elif args.suite == "both":
            output_path = french_full_dir / f"{filename}.wav"
        else:
            output_path = french_target_dir / f"{filename}.wav"
        if generate_audio(text, str(output_path), str(french_model)):
            french_success += 1

    print(f"\n  ✓ Generated {french_success}/{len(french_phrases)} French files")

    # Generate English audio
    english_success = 0
    if "en" in languages_to_generate:
        print(f"\n📢 Generating English test audio ({len(ENGLISH_PHRASES)} files)...")
        for filename, text in ENGLISH_PHRASES:
            output_path = english_dir / f"{filename}.wav"
            if generate_audio(text, str(output_path), str(english_model)):
                english_success += 1

        print(f"\n  ✓ Generated {english_success}/{len(ENGLISH_PHRASES)} English files")

    # Summary
    print("\n" + "=" * 60)
    print("Summary:")
    if "fr" in languages_to_generate:
        if args.suite == "basic":
            print(f"  French (basic): {french_success}/{len(french_phrases)} files in {french_dir}")
        elif args.suite == "full":
            print(f"  French (full): {french_success}/{len(french_phrases)} files in {french_full_dir}")
        else:
            print(f"  French (basic+full): {french_success}/{len(french_phrases)} files in {french_dir} + {french_full_dir}")
    if "en" in languages_to_generate:
        print(f"  English: {english_success}/{len(ENGLISH_PHRASES)} files in {english_dir}")
    print("=" * 60)

    total_expected = 0
    if "fr" in languages_to_generate:
        total_expected += len(french_phrases)
    if "en" in languages_to_generate:
        total_expected += len(ENGLISH_PHRASES)
    total_generated = french_success + english_success

    if total_generated == total_expected:
        print("\n✅ All test audio files generated successfully!")
        return 0
    else:
        print(f"\n⚠️  Warning: Only {total_generated}/{total_expected} files generated")
        return 1


if __name__ == "__main__":
    sys.exit(main())
