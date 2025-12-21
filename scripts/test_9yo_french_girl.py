#!/usr/bin/env python3
"""
9-Year-Old French Girl Test - Natural Kid Queries

How a real kid would ask for each song in the library.
"""

import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.intent_engine import IntentEngine
from modules.music_library import MusicLibrary
import logging

logging.basicConfig(level=logging.WARNING, format='%(message)s')


def test_9yo_queries():
    """Test how a 9-year-old French girl would ask for songs"""

    # Setup
    intent_engine = IntentEngine(language='fr', fuzzy_threshold=50, debug=False)
    music_library = MusicLibrary(
        library_path='playlist',
        fuzzy_threshold=35,
        phonetic_enabled=True,
        phonetic_weight=0.6,
        debug=False
    )
    music_library.load_from_filesystem()

    # Natural kid queries for each song in library
    test_cases = [
        # Song in library → How kid asks for it
        ("ABBA - Gimme! Gimme! Gimme!", "Joue gimme gimme gimme"),
        ("Air - Another Day", "Joue air"),
        ("Air - Electronic Performers", "Joue air"),
        ("Alessandra - Queen of Kings", "Joue queen of kings"),
        ("All For Metal - Gods of Metal", "Joue gods of metal"),
        ("Baby Lasagna - Rim Tim Tagi Dim", "Joue rim tim tagi dim"),
        ("Bruno Pelletier - Le val d'amour", "Joue le val d'amour"),
        ("Clara Ysé - Mama", "Joue mama"),
        ("Début De Soirée - Nuit de folie", "Joue nuit de folie"),
        ("Gala - Freed From Desire", "Joue freed from desire"),
        ("Grand Corps Malade - Mais je t'aime", "Joue mais je t'aime"),
        ("Grand Corps Malade, Louane - Derrière le brouillard", "Joue derrière le brouillard"),
        ("Images - Les Démons De Minuit", "Joue les démons de minuit"),
        ("Imagine Dragons - Believer", "Joue believer"),
        ("KOD - Chacun sa route", "Joue chacun sa route"),
        ("Kids United - On écrit sur les murs", "Joue on écrit sur les murs"),
        ("Kids United Nouvelle Generation - L'hymne de la vie", "Joue l'hymne de la vie"),
        ("Kids United - Le lion est mort ce soir", "Joue le lion est mort ce soir"),
        ("Kids United - Mama Africa", "Joue mama africa"),
        ("Louane - Jour 1", "Joue jour 1"),
        ("Louane - On était beau", "Joue on était beau"),
        ("Louane - Si t'étais là", "Joue si t'étais là"),
        ("Louane - maman", "Joue maman"),
        ("MIKA - Grace Kelly", "Joue grace kelly"),
        ("MIKA - Relax, Take It Easy", "Joue relax"),
        ("Magic System - Magic in the Air", "Joue magic in the air"),
        ("Monster High - Coming Out of the Dark", "Joue monster high"),
        ("Monster High - Royally Rule This World", "Joue monster high"),
        ("Nemo - The Code", "Joue the code"),
        ("Philippe Katerine - Sexy Cool", "Joue sexy cool"),
        ("RJD2 - Ghostwriter", "Joue ghostwriter"),
        ("Rob - Adentro", "Joue adentro"),
        ("Stromae - Alors on danse", "Joue alors on danse"),
        ("The Minions - Papaya", "Joue papaya"),
        ("Vicetone - Astronomia", "Joue astronomia"),
        ("Éric Serra - Deep Blue Dream", "Joue deep blue dream"),
        ("Éric Serra - The Big Blue", "Joue the big blue"),
        ("Yurtseven Kardeşler - Sevdalıyım", "Joue sevdaliyim"),
    ]

    print("=" * 80)
    print("9-YEAR-OLD FRENCH GIRL TEST")
    print("Natural kid queries for all 38 songs")
    print("=" * 80)
    print()

    results = {'perfect': 0, 'good': 0, 'ok': 0, 'wrong': 0}

    for expected_song, query in test_cases:
        # Extract intent
        intent = intent_engine.classify(query)
        if not intent or intent.intent_type != 'play_music':
            print(f"❌ '{query}' → Intent failed")
            results['wrong'] += 1
            continue

        extracted = intent.parameters.get('query', '')

        # Search
        result = music_library.search_best(extracted)
        if not result:
            print(f"❌ '{query}' → No match")
            results['wrong'] += 1
            continue

        matched_file, confidence = result
        matched_name = os.path.basename(matched_file)

        # Check if correct song
        song_key = expected_song.split(' - ')[0].lower()
        if song_key in matched_name.lower():
            if confidence >= 0.80:
                print(f"✅ '{query}' → {matched_name} ({confidence:.0%})")
                results['perfect'] += 1
            elif confidence >= 0.60:
                print(f"✅ '{query}' → {matched_name} ({confidence:.0%})")
                results['good'] += 1
            else:
                print(f"⚠️  '{query}' → {matched_name} ({confidence:.0%})")
                results['ok'] += 1
        else:
            print(f"❌ '{query}' → WRONG: {matched_name} (expected: {expected_song})")
            results['wrong'] += 1

    # Summary
    total = len(test_cases)
    print()
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print(f"Total songs:     {total}")
    print(f"✅ Perfect (≥80%): {results['perfect']} ({results['perfect']/total*100:.0f}%)")
    print(f"✅ Good (≥60%):    {results['good']} ({results['good']/total*100:.0f}%)")
    print(f"⚠️  OK (<60%):     {results['ok']} ({results['ok']/total*100:.0f}%)")
    print(f"❌ Wrong/Failed:  {results['wrong']} ({results['wrong']/total*100:.0f}%)")
    print()
    success_rate = (results['perfect'] + results['good'] + results['ok']) / total * 100
    print(f"Overall: {success_rate:.0f}% correct songs found")
    print()

    if success_rate == 100:
        print("🎉 PERFECT - Every song found!")
    elif success_rate >= 90:
        print("🎉 EXCELLENT - Production ready!")
    elif success_rate >= 80:
        print("✅ GOOD - Minor improvements possible")
    else:
        print("⚠️  NEEDS WORK")


if __name__ == '__main__':
    test_9yo_queries()
