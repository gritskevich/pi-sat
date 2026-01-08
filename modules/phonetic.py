"""
Phonetic encoding utilities for French voice matching.

Provides unified phonetic encoding for both intent matching and music search.
Uses FONEM algorithm (French-specific, 75x faster than BeiderMorse).
"""

import re
import unicodedata
from typing import Dict, Optional

# Try to import phonetic algorithms
try:
    from abydos.phonetic import FONEM
    FONEM_AVAILABLE = True
except ImportError:
    FONEM_AVAILABLE = False
    FONEM = None

try:
    from abydos.phonetic import BeiderMorse
    BEIDERMORSE_AVAILABLE = True
except ImportError:
    BEIDERMORSE_AVAILABLE = False
    BeiderMorse = None


class PhoneticEncoder:
    """
    Phonetic encoder with caching for pattern matching.

    Design:
    - Cache pattern encodings (limited set, e.g., ~20 intent patterns or ~400 music variants)
    - Never cache user query encodings (unbounded, causes memory leaks)
    """

    def __init__(self, algorithm: str = "fonem"):
        """
        Initialize phonetic encoder.

        Args:
            algorithm: Phonetic algorithm to use
                - "fonem": French-specific, fast (0.1ms), 78.6% accuracy
                - "beidermorse": Multilingual (16+ languages), slow (5ms), 71.4% accuracy
        """
        self.algorithm = algorithm
        self._matcher = None
        self._pattern_cache: Dict[str, str] = {}
        self._enabled = False

        if algorithm == "fonem":
            if FONEM_AVAILABLE:
                try:
                    self._matcher = FONEM()
                    self._enabled = True
                except Exception:
                    pass
        elif algorithm == "beidermorse":
            if BEIDERMORSE_AVAILABLE:
                try:
                    self._matcher = BeiderMorse(
                        language_arg=0,      # Auto-detect language
                        name_mode='gen',     # General mode
                        match_mode='approx'  # Approximate matching
                    )
                    self._enabled = True
                except Exception:
                    pass

    def is_available(self) -> bool:
        """Check if phonetic encoding is available"""
        return self._enabled and self._matcher is not None

    def encode_pattern(self, text: str) -> str:
        """
        Encode a pattern (intent trigger or music variant) with caching.

        Use this for fixed patterns that will be matched many times.
        """
        if not self.is_available():
            return ""

        normalized = self._normalize(text)
        if not normalized or not self._is_allowed(normalized):
            return ""

        # Check cache
        cached = self._pattern_cache.get(normalized)
        if cached is not None:
            return cached

        # Encode and cache
        encoded = self._encode_text(normalized)
        self._pattern_cache[normalized] = encoded
        return encoded

    def encode_query(self, text: str) -> str:
        """
        Encode a user query without caching.

        Use this for one-time user inputs that won't be reused.
        NEVER cache queries - causes memory leaks!
        """
        if not self.is_available():
            return ""

        normalized = self._normalize(text)
        if not normalized or not self._is_allowed(normalized):
            return ""

        return self._encode_text(normalized)

    def _encode_text(self, text: str) -> str:
        """Low-level encoding (internal use only)"""
        try:
            encoded = self._matcher.encode(text)
            # Handle different return types (string, tuple, etc.)
            if isinstance(encoded, tuple):
                return '|'.join(sorted(encoded))
            return str(encoded)
        except Exception:
            return ""

    def _normalize(self, text: str) -> str:
        """Normalize text for phonetic encoding"""
        if not text:
            return ""

        # Unicode normalization (remove accents)
        normalized = unicodedata.normalize('NFKD', text.lower())
        normalized = ''.join(ch for ch in normalized if not unicodedata.combining(ch))

        # Remove non-alphanumeric
        normalized = re.sub(r'[^a-z0-9]+', '', normalized).strip()

        return normalized

    def _is_allowed(self, normalized_text: str) -> bool:
        """Check if text is suitable for phonetic encoding"""
        # Require at least 3 characters for meaningful phonetic encoding
        return len(normalized_text) >= 3

    def clear_cache(self):
        """Clear pattern cache (useful for testing or memory management)"""
        self._pattern_cache.clear()

    def cache_size(self) -> int:
        """Get current cache size"""
        return len(self._pattern_cache)


# Convenience functions for quick access
_default_encoder: Optional[PhoneticEncoder] = None


def get_default_encoder() -> PhoneticEncoder:
    """Get or create the default phonetic encoder (FONEM)"""
    global _default_encoder
    if _default_encoder is None:
        _default_encoder = PhoneticEncoder(algorithm="fonem")
    return _default_encoder


def encode_pattern(text: str) -> str:
    """Encode a pattern using the default encoder"""
    return get_default_encoder().encode_pattern(text)


def encode_query(text: str) -> str:
    """Encode a query using the default encoder"""
    return get_default_encoder().encode_query(text)


def is_available() -> bool:
    """Check if phonetic encoding is available"""
    return get_default_encoder().is_available()
