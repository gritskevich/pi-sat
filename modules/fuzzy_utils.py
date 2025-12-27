"""Fuzzy string matching utilities

Shared utilities for fuzzy string matching used by intent classification and music search.
Following KISS and DRY principles - provides common fuzzy matching interface.

This module decouples MusicLibrary from IntentEngine by providing shared fuzzy matching
functionality without the intent classification logic.
"""

from thefuzz import fuzz
import config
from typing import List, Tuple


def fuzzy_match(query: str, pattern: str, threshold: int = None, use_levenshtein: bool = None) -> int:
    """
    Compute fuzzy match score between query and pattern.

    Args:
        query: Input string to match
        pattern: Pattern to match against
        threshold: Minimum score to consider a match (default: config.FUZZY_MATCH_THRESHOLD)
        use_levenshtein: Use Levenshtein distance (default: config.FUZZY_USE_LEVENSHTEIN)
                        - True: fuzz.ratio (exact matching, more strict)
                        - False: fuzz.partial_ratio (substring matching, more lenient)

    Returns:
        Match score (0-100), or 0 if below threshold

    Example:
        >>> fuzzy_match("alexa joue frozen", "joue {song}", threshold=50)
        75
        >>> fuzzy_match("play frozen", "joue {song}", threshold=80)
        0  # Below threshold
    """
    if threshold is None:
        threshold = config.FUZZY_MATCH_THRESHOLD
    if use_levenshtein is None:
        use_levenshtein = config.FUZZY_USE_LEVENSHTEIN

    if use_levenshtein:
        score = fuzz.ratio(query.lower(), pattern.lower())
    else:
        score = fuzz.partial_ratio(query.lower(), pattern.lower())

    return score if score >= threshold else 0


def fuzzy_match_list(query: str, candidates: List[str], threshold: int = None, limit: int = 5) -> List[Tuple[str, int]]:
    """
    Find best fuzzy matches from a list of candidates.

    Args:
        query: Input string to match
        candidates: List of strings to match against
        threshold: Minimum score (default: config.FUZZY_MATCH_THRESHOLD)
        limit: Maximum results to return (0 = unlimited)

    Returns:
        List of (candidate, score) tuples, sorted by score descending

    Example:
        >>> songs = ["Frozen", "Frozen 2", "The Frozen Ground", "Brave"]
        >>> fuzzy_match_list("frozen", songs, threshold=50, limit=3)
        [('Frozen', 100), ('Frozen 2', 91), ('The Frozen Ground', 75)]
    """
    if threshold is None:
        threshold = config.FUZZY_MATCH_THRESHOLD

    matches = []
    for candidate in candidates:
        score = fuzzy_match(query, candidate, threshold)
        if score > 0:
            matches.append((candidate, score))

    # Sort by score descending
    matches.sort(key=lambda x: x[1], reverse=True)

    # Apply limit if specified
    if limit > 0:
        return matches[:limit]
    return matches


def fuzzy_match_best(query: str, candidates: List[str], threshold: int = None) -> Tuple[str, int]:
    """
    Find single best fuzzy match from a list of candidates.

    Args:
        query: Input string to match
        candidates: List of strings to match against
        threshold: Minimum score (default: config.FUZZY_MATCH_THRESHOLD)

    Returns:
        Tuple of (best_candidate, score) or (None, 0) if no match above threshold

    Example:
        >>> songs = ["Frozen", "Brave", "Moana"]
        >>> fuzzy_match_best("frzen", songs)
        ('Frozen', 92)
        >>> fuzzy_match_best("xyz", songs, threshold=80)
        (None, 0)
    """
    matches = fuzzy_match_list(query, candidates, threshold, limit=1)
    if matches:
        return matches[0]
    return (None, 0)
