#!/usr/bin/env python3
"""
Real Library Phonetic Search Test
Test phonetic search with actual pi-sat playlist library (40 songs)
"""

import sys
import os
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.music_library import MusicLibrary

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)

def test_real_library():
    """Test phonetic search with real music library"""

    print("=" * 80)
    print("PHONETIC SEARCH TEST - REAL LIBRARY (playlist/)")
    print("=" * 80)
    print()

    # Initialize library with real playlist
    library_path = os.path.join(os.path.dirname(__file__), '..', 'playlist')
    library = MusicLibrary(
        library_path=library_path,
        fuzzy_threshold=35,  # Lower threshold for phonetic matching
        phonetic_enabled=True,
        phonetic_weight=0.6,
        debug=False
    )

    # Load catalog
    print(f"Loading music from: {library_path}")
    count = library.load_from_filesystem()
    print(f"✓ Loaded {count} songs")
    print(f"✓ Phonetic matching: {'enabled' if library.phonetic_enabled else 'disabled'}")
    print()

    if count == 0:
        print("❌ No songs found!")
        return

    # Test cases: How a French kid would pronounce these English names
    print("=" * 80)
    print("TEST CASES - French Pronunciation → English Artist Names")
    print("=" * 80)
    print()

    test_cases = [
        # English artists - French pronunciation
        ("aba", "ABBA", "ABBA - Gimme! Gimme! Gimme!"),
        ("imajine dragons", "Imagine Dragons", "Imagine Dragons - Believer"),
        ("mika", "MIKA", "MIKA - Grace Kelly"),
        ("ére", "Air", "Air - Another Day or Electronic Performers"),
        ("louane", "Louane", "Louane - Any song"),
        ("gala", "Gala", "Gala, Molella - Freed From Desire"),
        ("stromé", "Stromae", "Stromae - Alors on danse"),

        # Partial/typo searches
        ("beleever", "Believer", "Imagine Dragons - Believer"),
        ("gimme gimme", "ABBA", "ABBA - Gimme! Gimme! Gimme!"),
        ("alors on danse", "Stromae", "Stromae - Alors on danse"),
        ("grace keli", "Grace Kelly", "MIKA - Grace Kelly"),
        ("freed from dizire", "Freed From Desire", "Gala - Freed From Desire"),

        # French artists (control - should work well)
        ("grand corps malade", "Grand Corps Malade", "Any Grand Corps Malade song"),
        ("kids united", "Kids United", "Kids United - Any song"),
        ("philippe katerine", "Philippe Katerine", "Philippe Katerine - Sexy Cool"),

        # Tricky ones
        ("eric serra", "Éric Serra", "Éric Serra - Deep Blue Dream"),
        ("monster high", "Monster High", "Monster High - Any song"),
        ("magic system", "Magic System", "Magic System - Magic in the Air"),

        # Common kid queries (partial)
        ("maman", "maman", "Louane - maman"),
        ("mama", "Mama", "Clara Ysé - Mama or Kids United - Mama Africa"),
        ("nuit de folie", "Nuit de folie", "Début De Soirée - Nuit de folie"),
    ]

    results = {
        'success': 0,
        'partial': 0,
        'failed': 0,
        'total': len(test_cases)
    }

    for i, (query, artist_or_song, expected_context) in enumerate(test_cases, 1):
        print(f"{i}. Query: '{query}'")
        print(f"   Expected: {expected_context}")

        result = library.search(query)

        if result:
            file_path, confidence = result
            filename = os.path.basename(file_path)

            # Check if match is relevant
            query_lower = query.lower()
            filename_lower = filename.lower()
            artist_lower = artist_or_song.lower()

            # Success: query or expected artist found in result
            is_success = (
                query_lower in filename_lower or
                artist_lower in filename_lower or
                any(word in filename_lower for word in query_lower.split() if len(word) > 3)
            )

            if is_success:
                print(f"   ✅ MATCH: {filename} ({confidence:.0%})")
                results['success'] += 1
            else:
                print(f"   ⚠️  PARTIAL: {filename} ({confidence:.0%})")
                results['partial'] += 1
        else:
            print(f"   ❌ FAILED: No match found")
            results['failed'] += 1

        print()

    # Summary
    print("=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    print(f"Total tests:   {results['total']}")
    print(f"✅ Success:    {results['success']} ({results['success']/results['total']*100:.0f}%)")
    print(f"⚠️  Partial:    {results['partial']} ({results['partial']/results['total']*100:.0f}%)")
    print(f"❌ Failed:     {results['failed']} ({results['failed']/results['total']*100:.0f}%)")
    print()

    # Accuracy calculation
    accuracy = (results['success'] + results['partial'] * 0.5) / results['total'] * 100
    print(f"Overall accuracy: {accuracy:.0f}%")
    print()

    if accuracy >= 80:
        print("🎉 EXCELLENT - Ready for production!")
    elif accuracy >= 60:
        print("✅ GOOD - Minor tuning recommended")
    else:
        print("⚠️  NEEDS IMPROVEMENT - Consider adjusting phonetic_weight")

    print()


def interactive_test():
    """Interactive testing with real library"""

    print("=" * 80)
    print("INTERACTIVE PHONETIC SEARCH - REAL LIBRARY")
    print("=" * 80)
    print()

    library_path = os.path.join(os.path.dirname(__file__), '..', 'playlist')
    library = MusicLibrary(
        library_path=library_path,
        fuzzy_threshold=40,
        phonetic_enabled=True,
        phonetic_weight=0.6,
        debug=True  # Show detailed scoring
    )

    count = library.load_from_filesystem()
    print(f"Loaded {count} songs from playlist/")
    print(f"Phonetic matching: {'enabled' if library.phonetic_enabled else 'disabled'}")
    print()

    # Show sample songs
    print("Sample songs in library:")
    all_songs = library.get_all_songs()
    for i, song in enumerate(all_songs[:10], 1):
        print(f"  {i}. {os.path.basename(song)}")
    if len(all_songs) > 10:
        print(f"  ... and {len(all_songs) - 10} more")
    print()

    print("Try some queries (or 'quit' to exit):")
    print("Examples: aba, imajine dragons, louane, gimme gimme")
    print()

    while True:
        try:
            query = input("Search query: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nExiting...")
            break

        if query.lower() in ('quit', 'exit', 'q'):
            break

        if not query:
            continue

        print()
        result = library.search(query)

        if result:
            file_path, confidence = result
            filename = os.path.basename(file_path)
            print(f"  ✅ FOUND: {filename}")
            print(f"  Confidence: {confidence:.0%}")
        else:
            print(f"  ❌ No match found")

        print()


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--interactive':
        interactive_test()
    else:
        test_real_library()
