#!/usr/bin/env python3
"""
Phonetic Search Prototype - Test different approaches for French→English music matching

Compares:
1. Text-only fuzzy matching (current approach)
2. Beider-Morse phonetic matching
3. Hybrid (text + phonetic combined)
"""

import sys
from typing import List, Tuple, Optional
from thefuzz import fuzz, process

# Try to import abydos (may not be installed yet)
try:
    from abydos.phonetic import BeiderMorse
    ABYDOS_AVAILABLE = True
except ImportError:
    ABYDOS_AVAILABLE = False
    print("⚠️  abydos not installed. Install with: pip install abydos")


class PhoneticSearchPrototype:
    """Prototype for testing phonetic search approaches"""

    def __init__(self, fuzzy_threshold: int = 50):
        self.fuzzy_threshold = fuzzy_threshold

        if ABYDOS_AVAILABLE:
            # Initialize Beider-Morse with auto-detect (0 = any language)
            self.bm = BeiderMorse(
                language_arg=0,      # Auto-detect language (0 = any)
                name_mode='gen',     # General mode
                match_mode='approx'  # Approximate matching
            )
        else:
            self.bm = None

    def search_text_only(self, query: str, library: List[str]) -> Optional[Tuple[str, float]]:
        """Current approach: text-only fuzzy matching"""
        result = process.extractOne(
            query,
            library,
            scorer=fuzz.token_set_ratio
        )

        if not result:
            return None

        matched, score = result[0], result[1]
        confidence = score / 100.0

        if score < self.fuzzy_threshold:
            return None

        return (matched, confidence)

    def search_phonetic_only(self, query: str, library: List[str]) -> Optional[Tuple[str, float]]:
        """Beider-Morse phonetic matching only"""
        if not ABYDOS_AVAILABLE or not self.bm:
            return None

        # Encode query to phonetic codes
        query_phonetic = self.bm.encode(query)

        best_match = None
        best_score = 0

        for song in library:
            # Encode song to phonetic codes
            song_phonetic = self.bm.encode(song)

            # Compare phonetic codes
            # Both encode() return tuples, so convert to strings for comparison
            query_str = '|'.join(sorted(query_phonetic)) if isinstance(query_phonetic, tuple) else str(query_phonetic)
            song_str = '|'.join(sorted(song_phonetic)) if isinstance(song_phonetic, tuple) else str(song_phonetic)

            # Fuzzy match the phonetic codes
            score = fuzz.token_set_ratio(query_str, song_str)

            if score > best_score:
                best_score = score
                best_match = song

        confidence = best_score / 100.0

        if best_score < self.fuzzy_threshold:
            return None

        return (best_match, confidence)

    def search_hybrid(self, query: str, library: List[str]) -> Optional[Tuple[str, float]]:
        """Hybrid: combine text fuzzy + phonetic matching"""
        if not ABYDOS_AVAILABLE or not self.bm:
            return self.search_text_only(query, library)

        # Encode query
        query_phonetic = self.bm.encode(query)
        query_phonetic_str = '|'.join(sorted(query_phonetic)) if isinstance(query_phonetic, tuple) else str(query_phonetic)

        best_match = None
        best_score = 0

        for song in library:
            # Text fuzzy score
            text_score = fuzz.token_set_ratio(query, song)

            # Phonetic score
            song_phonetic = self.bm.encode(song)
            song_phonetic_str = '|'.join(sorted(song_phonetic)) if isinstance(song_phonetic, tuple) else str(song_phonetic)
            phonetic_score = fuzz.token_set_ratio(query_phonetic_str, song_phonetic_str)

            # Combined score (weighted)
            # 40% text, 60% phonetic (favor phonetic for cross-language)
            combined_score = (text_score * 0.4) + (phonetic_score * 0.6)

            if combined_score > best_score:
                best_score = combined_score
                best_match = song

        confidence = best_score / 100.0

        if best_score < self.fuzzy_threshold:
            return None

        return (best_match, confidence)


def test_phonetic_search():
    """Test phonetic search with real French→English examples"""

    print("=" * 80)
    print("PHONETIC SEARCH PROTOTYPE TEST")
    print("=" * 80)
    print()

    if not ABYDOS_AVAILABLE:
        print("❌ Cannot run tests - abydos not installed")
        print("   Install with: pip install abydos")
        return

    # Simulated music library (playlist-style kid favorites)
    library = [
        "Louane - maman",
        "Louane - Jour 1",
        "Kids United - On écrit sur les murs",
        "Kids United - Le lion est mort ce soir",
        "Stromae - Alors on danse",
        "Magic System - Magic in the Air",
        "MIKA - Grace Kelly",
        "Alessandra - Queen of Kings",
        "Monster High - Royally Rule This World",
        "The Minions - Papaya - Vaya Papayas",
    ]

    # Test cases: French pronunciations / typos for playlist names
    test_cases = [
        # (French input, Expected match, Description)
        ("louanne", "Louane - maman", "Typo in artist name"),
        ("maman", "Louane - maman", "Exact song title"),
        ("kids uniteed", "Kids United - On écrit sur les murs", "Typo in artist name"),
        ("lion est mort ce soir", "Kids United - Le lion est mort ce soir", "Partial title"),
        ("alor on danse", "Stromae - Alors on danse", "Typo in title"),
        ("magic in the air", "Magic System - Magic in the Air", "English control"),
        ("grace kely", "MIKA - Grace Kelly", "Typo in title"),
        ("queen of kings", "Alessandra - Queen of Kings", "Exact title"),
        ("papaya", "The Minions - Papaya - Vaya Papayas", "Partial title"),
        ("royally rule", "Monster High - Royally Rule This World", "Partial title"),
    ]

    searcher = PhoneticSearchPrototype(fuzzy_threshold=50)

    print(f"Library size: {len(library)} songs\n")

    for query, expected, description in test_cases:
        print(f"Query: '{query}' ({description})")
        print(f"Expected: {expected}")
        print()

        # Test 1: Text-only (current approach)
        result_text = searcher.search_text_only(query, library)
        if result_text:
            match, conf = result_text
            status = "✅" if match == expected else "❌"
            print(f"  {status} Text-only:     {match} ({conf:.2%})")
        else:
            print(f"  ❌ Text-only:     No match")

        # Test 2: Phonetic-only
        result_phonetic = searcher.search_phonetic_only(query, library)
        if result_phonetic:
            match, conf = result_phonetic
            status = "✅" if match == expected else "❌"
            print(f"  {status} Phonetic-only: {match} ({conf:.2%})")
        else:
            print(f"  ❌ Phonetic-only: No match")

        # Test 3: Hybrid
        result_hybrid = searcher.search_hybrid(query, library)
        if result_hybrid:
            match, conf = result_hybrid
            status = "✅" if match == expected else "❌"
            print(f"  {status} Hybrid:        {match} ({conf:.2%})")
        else:
            print(f"  ❌ Hybrid:        No match")

        print()
        print("-" * 80)
        print()

    print()
    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)


def interactive_test():
    """Interactive phonetic search testing"""
    if not ABYDOS_AVAILABLE:
        print("❌ abydos not installed. Install with: pip install abydos")
        return

    print("=" * 80)
    print("INTERACTIVE PHONETIC SEARCH TEST")
    print("=" * 80)
    print()

    library = [
        "Louane - maman",
        "Louane - Jour 1",
        "Kids United - On écrit sur les murs",
        "Stromae - Alors on danse",
        "MIKA - Grace Kelly",
    ]

    print("Music Library:")
    for i, song in enumerate(library, 1):
        print(f"  {i}. {song}")
    print()

    searcher = PhoneticSearchPrototype(fuzzy_threshold=40)
    bm = BeiderMorse(language_arg=0, match_mode='approx')

    print("Try some queries (or 'quit' to exit):")
    print("Examples: louanne, kids uniteed, alor on danse, grace kely")
    print()

    while True:
        query = input("Search query: ").strip()

        if query.lower() in ('quit', 'exit', 'q'):
            break

        if not query:
            continue

        print()

        # Show phonetic encoding
        query_phonetic = bm.encode(query)
        print(f"  Phonetic code: {query_phonetic}")
        print()

        # Search with all methods
        result_text = searcher.search_text_only(query, library)
        result_phonetic = searcher.search_phonetic_only(query, library)
        result_hybrid = searcher.search_hybrid(query, library)

        print(f"  Text-only:     {result_text}")
        print(f"  Phonetic-only: {result_phonetic}")
        print(f"  Hybrid:        {result_hybrid}")
        print()


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--interactive':
        interactive_test()
    else:
        test_phonetic_search()
