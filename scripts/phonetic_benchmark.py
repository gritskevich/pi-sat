#!/usr/bin/env python3
"""
Phonetic Algorithm Benchmark for French Music Search

Compares different phonetic algorithms for matching STT transcriptions
to actual song names in the music library.

Usage:
    python scripts/phonetic_benchmark.py
    python scripts/phonetic_benchmark.py --debug
"""

import os
import sys
import time
import argparse
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from thefuzz import fuzz

# Import available phonetic algorithms from abydos
try:
    from abydos.phonetic import (
        BeiderMorse,      # Multilingual (16+ languages), very accurate
        Soundex,          # Classic English algorithm
        Metaphone,        # English phonetic
        DoubleMetaphone,  # Improved Metaphone with multilingual support
        FONEM,            # French-specific
        Phonex,           # French-specific (improved Soundex for French)
    )
    PHONETIC_AVAILABLE = True
except ImportError as e:
    print(f"Error: abydos library not available: {e}")
    print("Install with: pip install abydos")
    sys.exit(1)


@dataclass
class MatchResult:
    """Result of a phonetic match attempt"""
    algorithm: str
    query: str
    expected: str
    matched: str
    confidence: float
    is_correct: bool
    encoding_time: float
    search_time: float


class PhoneticMatcher:
    """Wrapper for phonetic matching algorithms"""

    def __init__(self, name: str, encoder):
        self.name = name
        self.encoder = encoder
        self._cache: Dict[str, str] = {}

    def encode(self, text: str) -> str:
        """Encode text phonetically with caching"""
        if not text:
            return ""

        cached = self._cache.get(text.lower())
        if cached is not None:
            return cached

        try:
            encoded = self.encoder.encode(text)
            # Handle different return types
            if isinstance(encoded, tuple):
                result = '|'.join(sorted(encoded))
            else:
                result = str(encoded)
        except Exception:
            result = ""

        self._cache[text.lower()] = result
        return result

    def score(self, text1: str, text2: str) -> float:
        """Score phonetic similarity (0-100)"""
        enc1 = self.encode(text1)
        enc2 = self.encode(text2)

        if not enc1 or not enc2:
            return 0.0

        return float(fuzz.token_set_ratio(enc1, enc2))


def load_music_catalog(music_dir: str) -> List[str]:
    """Load song names from music directory"""
    catalog = []

    if not os.path.exists(music_dir):
        print(f"Error: Music directory not found: {music_dir}")
        return catalog

    for file in os.listdir(music_dir):
        if file.endswith('.mp3'):
            # Remove extension
            song_name = os.path.splitext(file)[0]
            catalog.append(song_name)

    return sorted(catalog)


def create_matchers() -> List[PhoneticMatcher]:
    """Initialize all phonetic matchers"""
    matchers = []

    # BeiderMorse (current - multilingual, 16+ languages)
    try:
        matchers.append(PhoneticMatcher(
            "BeiderMorse",
            BeiderMorse(language_arg=0, name_mode='gen', match_mode='approx')
        ))
    except Exception as e:
        print(f"Warning: BeiderMorse init failed: {e}")

    # Classic Soundex (English-focused)
    try:
        matchers.append(PhoneticMatcher("Soundex", Soundex()))
    except Exception as e:
        print(f"Warning: Soundex init failed: {e}")

    # Metaphone (English phonetic)
    try:
        matchers.append(PhoneticMatcher("Metaphone", Metaphone()))
    except Exception as e:
        print(f"Warning: Metaphone init failed: {e}")

    # Double Metaphone (improved, some multilingual support)
    try:
        matchers.append(PhoneticMatcher("DoubleMetaphone", DoubleMetaphone()))
    except Exception as e:
        print(f"Warning: DoubleMetaphone init failed: {e}")

    # FONEM (French-specific)
    try:
        matchers.append(PhoneticMatcher("FONEM", FONEM()))
    except Exception as e:
        print(f"Warning: FONEM init failed: {e}")

    # Phonex (French-specific, improved Soundex)
    try:
        matchers.append(PhoneticMatcher("Phonex", Phonex()))
    except Exception as e:
        print(f"Warning: Phonex init failed: {e}")

    return matchers


def search_catalog(
    query: str,
    catalog: List[str],
    matcher: PhoneticMatcher,
    text_weight: float = 0.4,
    phonetic_weight: float = 0.6
) -> Tuple[str, float, float, float]:
    """
    Search catalog using hybrid text + phonetic matching

    Returns:
        (best_match, confidence, encoding_time, search_time)
    """
    # Time phonetic encoding
    t0 = time.perf_counter()
    query_phonetic = matcher.encode(query)
    encoding_time = time.perf_counter() - t0

    # Time search
    t0 = time.perf_counter()

    best_match = None
    best_score = 0.0

    for song in catalog:
        # Text-only score
        text_score = fuzz.token_set_ratio(query, song)

        # Phonetic score
        phonetic_score = 0.0
        if query_phonetic:
            song_phonetic = matcher.encode(song)
            if song_phonetic:
                phonetic_score = fuzz.token_set_ratio(query_phonetic, song_phonetic)

        # Combined score
        combined = (text_score * text_weight) + (phonetic_score * phonetic_weight)

        if combined > best_score:
            best_score = combined
            best_match = song

    search_time = time.perf_counter() - t0

    confidence = best_score / 100.0
    return best_match, confidence, encoding_time, search_time


def run_benchmark(
    test_cases: List[Tuple[str, str]],
    catalog: List[str],
    matchers: List[PhoneticMatcher],
    debug: bool = False
) -> Dict[str, List[MatchResult]]:
    """
    Run benchmark on all test cases and algorithms

    Args:
        test_cases: List of (query, expected_song) tuples
        catalog: Full music catalog
        matchers: List of phonetic matchers to test
        debug: Print detailed results

    Returns:
        Dict mapping algorithm name to list of match results
    """
    results = {m.name: [] for m in matchers}

    print(f"\n{'='*80}")
    print(f"Running benchmark: {len(test_cases)} test cases × {len(matchers)} algorithms")
    print(f"{'='*80}\n")

    for i, (query, expected) in enumerate(test_cases, 1):
        if debug:
            print(f"\n[{i}/{len(test_cases)}] Query: '{query}' → Expected: '{expected}'")

        for matcher in matchers:
            matched, confidence, enc_time, search_time = search_catalog(
                query, catalog, matcher
            )

            is_correct = matched == expected if matched else False

            result = MatchResult(
                algorithm=matcher.name,
                query=query,
                expected=expected,
                matched=matched or "",
                confidence=confidence,
                is_correct=is_correct,
                encoding_time=enc_time,
                search_time=search_time
            )

            results[matcher.name].append(result)

            if debug:
                status = "✓" if is_correct else "✗"
                print(f"  {status} {matcher.name:20s}: '{matched}' ({confidence:.1%}) "
                      f"[enc: {enc_time*1000:.1f}ms, search: {search_time*1000:.1f}ms]")

    return results


def print_summary(results: Dict[str, List[MatchResult]]):
    """Print benchmark summary statistics"""
    print(f"\n{'='*80}")
    print("BENCHMARK SUMMARY")
    print(f"{'='*80}\n")

    print(f"{'Algorithm':<20} {'Accuracy':<12} {'Avg Conf':<12} {'Encoding':<15} {'Search':<15}")
    print(f"{'-'*80}")

    for algo_name, matches in results.items():
        total = len(matches)
        correct = sum(1 for m in matches if m.is_correct)
        accuracy = correct / total if total > 0 else 0.0

        avg_confidence = sum(m.confidence for m in matches) / total if total > 0 else 0.0
        avg_encoding = sum(m.encoding_time for m in matches) / total if total > 0 else 0.0
        avg_search = sum(m.search_time for m in matches) / total if total > 0 else 0.0

        print(f"{algo_name:<20} {accuracy:>6.1%} ({correct}/{total})  "
              f"{avg_confidence:>6.1%}      "
              f"{avg_encoding*1000:>6.1f}ms        "
              f"{avg_search*1000:>6.1f}ms")

    print()


def create_test_cases() -> List[Tuple[str, str]]:
    """
    Create realistic test cases based on STT errors

    These represent actual misrecognitions from Whisper STT,
    not just typos but phonetically similar words.
    """
    test_cases = [
        # Perfect matches (baseline)
        ("astronomia", "Vicetone, Tony Igy - Astronomia"),
        ("frozen", "La Reine des neiges"),  # Note: This won't be in catalog
        ("stromae", "Stromae - Alors on danse - Radio Edit"),

        # French STT errors - phonetic similarity
        ("astronomi", "Vicetone, Tony Igy - Astronomia"),  # Missing final 'a'
        ("astronomie", "Vicetone, Tony Igy - Astronomia"),  # French spelling
        ("astronomie à", "Vicetone, Tony Igy - Astronomia"),  # With filler word
        ("astro nomia", "Vicetone, Tony Igy - Astronomia"),  # Space inserted

        ("mais je t'aime", "Grand Corps Malade, Camille Lellouche - Mais je t'aime"),
        ("mais je taime", "Grand Corps Malade, Camille Lellouche - Mais je t'aime"),
        ("mé je t'aime", "Grand Corps Malade, Camille Lellouche - Mais je t'aime"),  # Phonetic 'ai' → 'é'

        ("lou anne mama", "Louane - maman"),  # Name mispronunciation
        ("louan maman", "Louane - maman"),
        ("louwane mama", "Louane - maman"),

        # English/French mixing
        ("air electronic performers", "Air - Electronic Performers"),
        ("air électronic performers", "Air - Electronic Performers"),  # French spelling
        ("air electronique", "Air - Electronic Performers"),  # Translated

        # Artist name errors
        ("grand corp malade mais je t'aime", "Grand Corps Malade, Camille Lellouche - Mais je t'aime"),
        ("grand cor malade", "Grand Corps Malade, Camille Lellouche - Mais je t'aime"),

        # Common French phonetic errors
        ("nuit de foli", "Début De Soirée - Nuit de folie"),  # Silent 'e'
        ("nui de folie", "Début De Soirée - Nuit de folie"),  # Missing 't'

        ("alors on dance", "Stromae - Alors on danse - Radio Edit"),  # English spelling
        ("alor on danse", "Stromae - Alors on danse - Radio Edit"),  # Missing 's'

        # Accent/diacritic removal
        ("eric serra deep blue", "Éric Serra - Deep Blue Dream"),
        ("debut de soiree", "Début De Soirée - Nuit de folie"),

        # Partial matches
        ("ghostwriter", "RJD2 - Ghostwriter"),
        ("ghost writer", "RJD2 - Ghostwriter"),
        ("rjd2", "RJD2 - Ghostwriter"),

        # Complete misrecognition (challenging)
        ("le monde s'est dédoublé", "Le monde s'est dédoublé"),
        ("le monde c'est dédoublé", "Le monde s'est dédoublé"),  # s'est → c'est
    ]

    return test_cases


def main():
    parser = argparse.ArgumentParser(description="Benchmark phonetic algorithms for music search")
    parser.add_argument("--debug", action="store_true", help="Show detailed per-test results")
    parser.add_argument("--music-dir", default=os.path.expanduser("~/Music"),
                        help="Music directory path")
    args = parser.parse_args()

    # Load catalog
    print(f"Loading music catalog from: {args.music_dir}")
    catalog = load_music_catalog(args.music_dir)
    print(f"Loaded {len(catalog)} songs\n")

    if not catalog:
        print("Error: No songs found in catalog")
        return 1

    # Create matchers
    print("Initializing phonetic matchers...")
    matchers = create_matchers()
    print(f"Loaded {len(matchers)} algorithms: {', '.join(m.name for m in matchers)}\n")

    if not matchers:
        print("Error: No phonetic matchers available")
        return 1

    # Create test cases
    test_cases = create_test_cases()

    # Filter test cases to only include songs in catalog
    valid_cases = []
    missing_songs = set()
    for query, expected in test_cases:
        if expected in catalog:
            valid_cases.append((query, expected))
        else:
            missing_songs.add(expected)

    if missing_songs:
        print(f"Note: {len(missing_songs)} test cases skipped (songs not in catalog):")
        for song in sorted(missing_songs):
            print(f"  - {song}")
        print()

    # Run benchmark
    results = run_benchmark(valid_cases, catalog, matchers, debug=args.debug)

    # Print summary
    print_summary(results)

    return 0


if __name__ == "__main__":
    sys.exit(main())
