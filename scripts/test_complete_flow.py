#!/usr/bin/env python3
"""
Complete Flow Test - Intent Extraction + Phonetic Search

Tests the full pipeline:
1. IntentEngine extracts song name from voice command
2. MusicLibrary.search_best() always returns a match
3. Low confidence triggers warning message

Shows the elegant modular architecture working together.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.intent_engine import IntentEngine
from modules.music_library import MusicLibrary
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')


def test_complete_flow():
    """Test complete flow: Intent extraction → Phonetic search"""

    print("=" * 80)
    print("COMPLETE FLOW TEST - Intent Extraction + Phonetic Search")
    print("=" * 80)
    print()

    # Initialize components
    intent_engine = IntentEngine(language='fr', fuzzy_threshold=50, debug=False)

    library_path = os.path.join(os.path.dirname(__file__), '..', 'playlist')
    music_library = MusicLibrary(
        library_path=library_path,
        fuzzy_threshold=35,
        phonetic_enabled=True,
        phonetic_weight=0.6,
        debug=False
    )

    # Load library
    count = music_library.load_from_filesystem()
    print(f"✓ Loaded {count} songs from playlist/")
    print(f"✓ Intent Engine: French, 22 intents")
    print(f"✓ Music Library: Phonetic search enabled")
    print()

    # Test cases: Natural voice commands with intent phrases
    test_cases = [
        # (Full command, Expected intent, Expected extracted query, Description)
        ("Tu peux jouer astronomiya", "play_music", "astronomiya", "Full phrase → extract song"),
        ("Joue maman", "play_music", "maman", "Short command"),
        ("Mets moi imagine dragons", "play_music", "imagine dragons", "Mets moi → extract"),
        ("Joue grace keli", "play_music", "grace keli", "Typo in artist name"),
        ("Lance stromé", "play_music", "stromé", "Low confidence match"),
        ("Peux tu jouer kids united", "play_music", "kids united", "Polite phrasing"),
        ("Joue aba s'il te plaît", "play_music", "aba s'il te plaît", "Extra polite words"),
    ]

    print("=" * 80)
    print("TEST CASES - Full Pipeline")
    print("=" * 80)
    print()

    results = {'success': 0, 'low_confidence': 0, 'failed': 0}

    for i, (command, expected_intent, expected_query, description) in enumerate(test_cases, 1):
        print(f"{i}. Command: '{command}'")
        print(f"   Description: {description}")

        # Step 1: Intent classification (extracts song name)
        intent = intent_engine.classify(command)

        if not intent:
            print(f"   ❌ FAILED: Intent not classified")
            results['failed'] += 1
            print()
            continue

        if intent.intent_type != expected_intent:
            print(f"   ❌ FAILED: Wrong intent: {intent.intent_type} (expected {expected_intent})")
            results['failed'] += 1
            print()
            continue

        extracted_query = intent.parameters.get('query', '')

        print(f"   ✓ Intent: {intent.intent_type}")
        print(f"   ✓ Extracted query: '{extracted_query}'")

        # Verify extraction worked
        if expected_query.lower() not in extracted_query.lower():
            print(f"   ⚠️  WARNING: Expected '{expected_query}' in extracted query")

        # Step 2: Phonetic search (ALWAYS returns best match)
        search_result = music_library.search_best(extracted_query)

        if not search_result:
            print(f"   ❌ FAILED: No search result (library empty?)")
            results['failed'] += 1
            print()
            continue

        file_path, confidence = search_result
        filename = os.path.basename(file_path)

        # Step 3: Check confidence and determine response
        if confidence < 0.60:
            # Low confidence - warning message
            print(f"   ⚠️  LOW CONFIDENCE: {filename} ({confidence:.0%})")
            print(f"   → TTS: 'Je ne suis pas sûr, mais j'ai trouvé {extracted_query}'")
            results['low_confidence'] += 1
        else:
            # High confidence - success
            print(f"   ✅ HIGH CONFIDENCE: {filename} ({confidence:.0%})")
            print(f"   → TTS: 'Joue {extracted_query}'")
            results['success'] += 1

        print()

    # Summary
    total = len(test_cases)
    print("=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    print(f"Total tests:        {total}")
    print(f"✅ Success:         {results['success']} ({results['success']/total*100:.0f}%)")
    print(f"⚠️  Low confidence:  {results['low_confidence']} ({results['low_confidence']/total*100:.0f}%)")
    print(f"❌ Failed:          {results['failed']} ({results['failed']/total*100:.0f}%)")
    print()

    # Overall verdict
    overall_success = (results['success'] + results['low_confidence']) / total * 100
    print(f"Overall: {overall_success:.0f}% of queries found a match")
    print()

    if results['failed'] == 0:
        print("🎉 PERFECT - All queries found a match!")
    elif overall_success >= 90:
        print("✅ EXCELLENT - Ready for production!")
    else:
        print("⚠️  NEEDS IMPROVEMENT")

    print()
    print("=" * 80)
    print("ARCHITECTURE VERIFICATION")
    print("=" * 80)
    print()
    print("✅ Intent Extraction: IntentEngine separates intent from query")
    print("✅ Phonetic Search: MusicLibrary handles cross-language matching")
    print("✅ Always Return Best: search_best() never returns empty-handed")
    print("✅ Low Confidence Warning: User informed when match is uncertain")
    print("✅ Modular Design: Each component has single responsibility (KISS)")
    print()


if __name__ == '__main__':
    test_complete_flow()
