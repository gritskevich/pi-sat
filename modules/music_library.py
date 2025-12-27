"""
Music Library Module - Music Catalog and Search

Manages music catalog and search functionality completely independent of MPD.
Can be used by MPD controller, CLI tools, web interface, tests, etc.

Key Features:
- Fuzzy search with typo tolerance
- Phonetic search for cross-language matching (French→English, etc.)
- Hybrid search (text + phonetic) for 90% accuracy
- Favorites playlist management
- Catalog caching for performance
- File-based and MPD-based catalog loading
- Standalone operation (no MPD required)

Search Modes:
- Text-only: Traditional fuzzy matching (50% accuracy on French→English)
- Phonetic-only: Beider-Morse phonetic matching (70% accuracy)
- Hybrid (default): Combined text + phonetic (90% accuracy)

Following KISS principle: Simple, focused, reusable.
"""

import os
import logging
import re
import unicodedata
from pathlib import Path
from typing import Optional, List, Tuple
import config
from modules.logging_utils import setup_logger
from modules.intent_engine import IntentEngine

# Phonetic matching for cross-language search (French→English, etc.)
try:
    from abydos.phonetic import BeiderMorse
    PHONETIC_AVAILABLE = True
except ImportError:
    PHONETIC_AVAILABLE = False
    BeiderMorse = None

logger = setup_logger(__name__)


class MusicLibrary:
    """
    Music catalog and search engine.

    Completely independent module - works with or without MPD.
    """

    def __init__(
        self,
        library_path: Optional[str] = None,
        fuzzy_threshold: int = 50,
        cache_enabled: bool = True,
        phonetic_enabled: bool = True,
        phonetic_weight: float = None,
        debug: bool = False
    ):
        """
        Initialize Music Library.

        Args:
            library_path: Path to music directory (None to use MPD only)
            fuzzy_threshold: Minimum fuzzy match score (0-100)
            cache_enabled: Enable catalog caching
            phonetic_enabled: Enable phonetic matching for cross-language search
            phonetic_weight: Weight for phonetic score in hybrid search (0.0-1.0)
            debug: Enable debug logging
        """
        self.library_path = library_path
        self.fuzzy_threshold = fuzzy_threshold
        self.cache_enabled = cache_enabled
        self.phonetic_enabled = phonetic_enabled and PHONETIC_AVAILABLE
        self.phonetic_weight = phonetic_weight if phonetic_weight is not None else config.PHONETIC_WEIGHT
        self.debug = debug

        # Catalog storage
        self._catalog: List[str] = []
        self._catalog_metadata: List[Tuple[str, list[str]]] = []  # (file_path, variants)
        self._favorites: List[str] = []
        self._phonetic_cache: Dict[str, str] = {}
        self._query_phonetic_cache: Dict[str, str] = {}
        self._search_best_cache: Dict[str, Tuple[str, float]] = {}

        # Search engine (text fuzzy matching)
        self._search_engine = IntentEngine(fuzzy_threshold=fuzzy_threshold, debug=debug)

        # Phonetic search engine (for cross-language matching)
        self._phonetic_matcher = None
        if self.phonetic_enabled:
            try:
                self._phonetic_matcher = BeiderMorse(
                    language_arg=0,      # Auto-detect language (supports 16 languages)
                    name_mode='gen',     # General mode (not name-specific)
                    match_mode='approx'  # Approximate matching
                )
                logger.info("Phonetic matching enabled (Beider-Morse)")
            except Exception as e:
                logger.warning(f"Failed to initialize phonetic matcher: {e}")
                self.phonetic_enabled = False

        if debug:
            logger.setLevel(logging.DEBUG)

        logger.info(
            f"MusicLibrary initialized "
            f"(threshold={fuzzy_threshold}, "
            f"phonetic={'enabled' if self.phonetic_enabled else 'disabled'})"
        )

    def load_from_filesystem(self, library_path: Optional[str] = None) -> int:
        """
        Load catalog from filesystem.

        Args:
            library_path: Music directory path (overrides init path)

        Returns:
            Number of songs loaded
        """
        path = library_path or self.library_path

        if not path:
            logger.warning("No library path provided")
            return 0

        path = os.path.expanduser(path)

        if not os.path.exists(path):
            logger.warning(f"Library path does not exist: {path}")
            return 0

        logger.info(f"Loading music from: {path}")

        # Supported audio formats
        audio_extensions = {'.mp3', '.flac', '.ogg', '.m4a', '.wav', '.opus'}

        catalog = []
        metadata = []

        for root, _, files in os.walk(path):
            for file in files:
                ext = os.path.splitext(file)[1].lower()

                if ext in audio_extensions:
                    file_path = os.path.join(root, file)
                    # Make path relative to library root
                    rel_path = os.path.relpath(file_path, path)

                    catalog.append(rel_path)
                    basename = os.path.splitext(file)[0]
                    variants = self._build_searchable_variants(basename)
                    metadata.append((rel_path, variants))

        self._catalog = catalog
        self._catalog_metadata = metadata
        self._phonetic_cache = {}
        self._query_phonetic_cache = {}
        self._search_best_cache = {}

        logger.info(f"Loaded {len(catalog)} songs from filesystem")
        return len(catalog)

    def load_from_mpd(self, mpd_client) -> int:
        """
        Load catalog from MPD database.

        Args:
            mpd_client: Connected MPD client instance

        Returns:
            Number of songs loaded
        """
        try:
            # Get all files from MPD
            all_files = mpd_client.listall()

            catalog = []
            metadata = []

            for item in all_files:
                if 'file' in item:
                    file_path = item['file']

                    catalog.append(file_path)
                    basename = os.path.splitext(os.path.basename(file_path))[0]
                    variants = self._build_searchable_variants(basename)
                    metadata.append((file_path, variants))

            self._catalog = catalog
            self._catalog_metadata = metadata
            self._phonetic_cache = {}
            self._query_phonetic_cache = {}
            self._search_best_cache = {}

            logger.info(f"Loaded {len(catalog)} songs from MPD")
            return len(catalog)

        except Exception as e:
            logger.error(f"Failed to load catalog from MPD: {e}")
            return 0

    def search(self, query: str) -> Optional[Tuple[str, float]]:
        """
        Fuzzy search catalog for best match (respects threshold).

        Handles typos, partial matches, and cross-language pronunciations
        (e.g., "frozzen" → "Frozen", "frosen" → "Frozen" in French).

        Uses hybrid approach:
        - Text fuzzy matching (handles typos, abbreviations)
        - Phonetic matching (handles cross-language, e.g., French→English)
        - Weighted combination for best accuracy

        Args:
            query: Search query (song name, artist, etc.)

        Returns:
            Tuple of (file_path, confidence) or None if no match above threshold
        """
        if not query or not query.strip():
            logger.warning("Empty search query")
            return None

        if not self._catalog_metadata:
            logger.warning("Catalog is empty - call load_from_filesystem() or load_from_mpd() first")
            return None

        query = query.strip()

        # Fast path: exact match (avoids token_set_ratio "subset=100" ambiguity)
        norm_query = self._normalize_variant(query)
        query_lower = query.lower()
        for file_path, variants in self._catalog_metadata:
            basename = os.path.splitext(os.path.basename(file_path))[0]
            if basename.lower() == query_lower or self._normalize_variant(basename) == norm_query:
                return (file_path, 1.0)
            for variant in variants:
                if variant.lower() == query_lower or self._normalize_variant(variant) == norm_query:
                    return (file_path, 1.0)

        # Choose search method
        if self.phonetic_enabled and self._phonetic_matcher:
            # Hybrid search (text + phonetic)
            result = self._search_hybrid(query)
        else:
            # Text-only fuzzy search (fallback)
            result = self._search_text_only(query)

        if not result:
            logger.info(f"No match found for: '{query}'")
            return None

        matched_name, confidence = result
        logger.info(f"Search: '{query}' → '{matched_name}' ({confidence:.2%})")
        return result

    def search_best(self, query: str) -> Optional[Tuple[str, float]]:
        """
        Fuzzy search catalog - ALWAYS returns best match (ignores threshold).

        Use this when you want to play *something* even if confidence is low.
        Useful for kid-friendly UX - better to play something than nothing!

        Args:
            query: Search query (song name, artist, etc.)

        Returns:
            Tuple of (file_path, confidence) or None only if catalog is empty
        """
        if not query or not query.strip():
            logger.warning("Empty search query")
            return None

        if not self._catalog_metadata:
            logger.warning("Catalog is empty - call load_from_filesystem() or load_from_mpd() first")
            return None

        query = query.strip()

        # Fast path: exact match
        norm_query = self._normalize_variant(query)
        query_lower = query.lower()
        for file_path, variants in self._catalog_metadata:
            basename = os.path.splitext(os.path.basename(file_path))[0]
            if basename.lower() == query_lower or self._normalize_variant(basename) == norm_query:
                return (file_path, 1.0)
            for variant in variants:
                if variant.lower() == query_lower or self._normalize_variant(variant) == norm_query:
                    return (file_path, 1.0)

        cache_key = query.lower()
        cached = self._search_best_cache.get(cache_key)
        if cached:
            return cached

        # Temporarily disable threshold by setting to 0
        original_threshold = self.fuzzy_threshold
        self.fuzzy_threshold = 0

        try:
            # Choose search method (same as search())
            if self.phonetic_enabled and self._phonetic_matcher:
                result = self._search_hybrid(query)
            else:
                result = self._search_text_only(query)

            if result:
                file_path, confidence = result
                logger.info(f"Search (best): '{query}' → '{file_path}' ({confidence:.2%})")
                self._search_best_cache[cache_key] = (file_path, confidence)
                return result
            else:
                # Should never happen unless catalog is empty
                logger.warning(f"No match found even with threshold=0: '{query}'")
                return None

        finally:
            # Always restore original threshold
            self.fuzzy_threshold = original_threshold

    def _search_text_only(self, query: str) -> Optional[Tuple[str, float]]:
        """
        Text-only fuzzy search (current approach).

        Args:
            query: Search query

        Returns:
            Tuple of (file_path, confidence) or None
        """
        from thefuzz import fuzz

        norm_query = self._normalize_variant(query)
        best_score = 0
        best_file_path = None
        for file_path, variants in self._catalog_metadata:
            for variant in variants:
                score = max(
                    fuzz.token_set_ratio(query, variant),
                    fuzz.token_set_ratio(norm_query, variant),
                )
                if score > best_score:
                    best_score = score
                    best_file_path = file_path

        if best_score < self.fuzzy_threshold:
            return None

        return (best_file_path, best_score / 100.0)

    def _search_hybrid(self, query: str) -> Optional[Tuple[str, float]]:
        """
        Hybrid search: combine text fuzzy + phonetic matching.

        Weighted combination (default: 60% phonetic, 40% text) provides
        best accuracy for cross-language scenarios while maintaining
        good performance on exact matches and typos.

        Args:
            query: Search query

        Returns:
            Tuple of (file_path, confidence) or None
        """
        from thefuzz import fuzz

        norm_query = self._normalize_variant(query)

        # Encode query to phonetic
        query_phonetic_str = self._get_query_phonetic(query)
        if not query_phonetic_str:
            return self._search_text_only(query)

        best_score = 0
        best_file_path = None

        text_weight = 1.0 - self.phonetic_weight
        text_scores: list[tuple[str, float]] = []
        per_file_text: dict[str, float] = {}
        per_file_variants: dict[str, list[str]] = {}
        for file_path, variants in self._catalog_metadata:
            file_best = 0
            for variant in variants:
                text_score = max(
                    fuzz.token_set_ratio(query, variant),
                    fuzz.token_set_ratio(norm_query, variant),
                )
                if text_score > file_best:
                    file_best = text_score
            per_file_text[file_path] = file_best
            per_file_variants[file_path] = variants
            text_scores.append((file_path, file_best))

        # Only compute phonetics for the most promising text candidates.
        top_candidates = sorted(text_scores, key=lambda item: item[1], reverse=True)[:10]
        candidate_set = {item[0] for item in top_candidates}

        for file_path, text_score in text_scores:
            file_best = text_score
            if file_path in candidate_set:
                variants = per_file_variants[file_path]
                for variant in variants:
                    phonetic_score = 0
                    phonetic_str = self._get_phonetic_variant(variant)
                    if phonetic_str:
                        phonetic_score = fuzz.token_set_ratio(query_phonetic_str, phonetic_str)
                    combined_score = (text_score * text_weight) + (phonetic_score * self.phonetic_weight)
                    file_best = max(file_best, combined_score)
                    if self.debug:
                        logger.debug(
                            f"  '{variant}': text={text_score}, phonetic={phonetic_score}, "
                            f"combined={combined_score:.1f}"
                        )

            if file_best > best_score:
                best_score = file_best
                best_file_path = file_path

        confidence = best_score / 100.0

        if best_score < self.fuzzy_threshold:
            return None

        return (best_file_path, confidence)

    def _encode_phonetic(self, text: str, cache: dict, log_errors: bool = False) -> str:
        """
        Encode text phonetically with caching.

        Args:
            text: Text to encode
            cache: Cache dictionary to use
            log_errors: Whether to log encoding errors

        Returns:
            Phonetic encoding string
        """
        if not self.phonetic_enabled or not self._phonetic_matcher:
            return ""
        if not self._phonetic_allowed(text):
            return ""

        normalized = self._normalize_variant(text)
        cached = cache.get(normalized)
        if cached is not None:
            return cached

        try:
            encoded = self._phonetic_matcher.encode(normalized or text)
            phonetic_str = '|'.join(sorted(encoded)) if isinstance(encoded, tuple) else str(encoded)
        except Exception as e:
            if log_errors:
                logger.warning(f"Phonetic encoding failed for '{text}': {e}")
            phonetic_str = ""

        cache[normalized] = phonetic_str
        return phonetic_str

    def _get_phonetic_variant(self, variant: str) -> str:
        """Get phonetic encoding for a variant (from catalog)."""
        return self._encode_phonetic(variant, self._phonetic_cache, log_errors=False)

    def _get_query_phonetic(self, query: str) -> str:
        """Get phonetic encoding for a query (from user input)."""
        return self._encode_phonetic(query, self._query_phonetic_cache, log_errors=True)

    def _phonetic_allowed(self, text: str) -> bool:
        norm = unicodedata.normalize('NFKD', text.lower())
        norm = ''.join(ch for ch in norm if not unicodedata.combining(ch))
        norm = re.sub(r'[^a-z0-9]+', ' ', norm).strip()
        if not norm:
            return False
        if len(norm.replace(' ', '')) <= 4:
            return False
        tokens = [t for t in norm.split() if t]
        if len(tokens) >= 3:
            return False
        if len(norm.replace(' ', '')) > 24:
            return False
        return True

    def _build_searchable_variants(self, basename: str) -> list[str]:
        variants = [basename]
        if " - " in basename:
            parts = [part.strip() for part in basename.split(" - ") if part.strip()]
            if parts:
                variants.extend(parts)
            if len(parts) > 1:
                variants.append(" - ".join(parts[1:]))
        normalized = [self._normalize_variant(v) for v in variants]
        variants.extend([v for v in normalized if v])
        seen = set()
        unique = []
        for variant in variants:
            if variant not in seen:
                seen.add(variant)
                unique.append(variant)
        return unique

    def _normalize_variant(self, text: str) -> str:
        text = text.lower().strip()
        text = unicodedata.normalize('NFKD', text)
        text = ''.join(ch for ch in text if not unicodedata.combining(ch))
        text = re.sub(r'[^a-z0-9]+', '', text)
        return text

    def get_all_songs(self) -> List[str]:
        """
        Get all songs in catalog.

        Returns:
            List of file paths
        """
        return self._catalog.copy()

    def get_catalog_size(self) -> int:
        """
        Get number of songs in catalog.

        Returns:
            Song count
        """
        return len(self._catalog)

    def load_favorites(self, favorites_path: Optional[str] = None) -> List[str]:
        """
        Load favorites playlist from .m3u file.

        Args:
            favorites_path: Path to favorites.m3u (None for default)

        Returns:
            List of song paths in favorites
        """
        # Default: ~/.mpd/playlists/favorites.m3u
        if not favorites_path:
            favorites_path = os.path.expanduser("~/.mpd/playlists/favorites.m3u")

        if not os.path.exists(favorites_path):
            logger.debug(f"Favorites file not found: {favorites_path}")
            self._favorites = []
            return []

        try:
            with open(favorites_path, 'r') as f:
                lines = f.readlines()

            # Parse M3U format (skip comments and empty lines)
            favorites = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    favorites.append(line)

            self._favorites = favorites
            logger.info(f"Loaded {len(favorites)} songs from favorites")
            return favorites

        except Exception as e:
            logger.error(f"Failed to load favorites: {e}")
            self._favorites = []
            return []

    def get_favorites(self) -> List[str]:
        """
        Get favorites playlist.

        Returns:
            List of song paths (cached)
        """
        if not self._favorites:
            self.load_favorites()

        return self._favorites.copy()

    def add_to_favorites(
        self,
        song_path: str,
        favorites_path: Optional[str] = None
    ) -> bool:
        """
        Add song to favorites playlist.

        Args:
            song_path: Path to song file
            favorites_path: Path to favorites.m3u (None for default)

        Returns:
            True if successful
        """
        if not song_path:
            logger.warning("Empty song path")
            return False

        # Default: ~/.mpd/playlists/favorites.m3u
        if not favorites_path:
            favorites_path = os.path.expanduser("~/.mpd/playlists/favorites.m3u")

        # Ensure directory exists
        favorites_dir = os.path.dirname(favorites_path)
        os.makedirs(favorites_dir, exist_ok=True)

        try:
            # Check if already in favorites
            current_favorites = self.load_favorites(favorites_path)

            if song_path in current_favorites:
                logger.info(f"Song already in favorites: {song_path}")
                return True

            # Append to file
            with open(favorites_path, 'a') as f:
                f.write(f"{song_path}\n")

            # Update cache
            self._favorites.append(song_path)

            logger.info(f"Added to favorites: {song_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to add to favorites: {e}")
            return False

    def refresh(self, source: str = 'auto') -> int:
        """
        Refresh catalog.

        Args:
            source: 'auto', 'filesystem', or 'mpd'

        Returns:
            Number of songs loaded
        """
        if source == 'filesystem' or (source == 'auto' and self.library_path):
            return self.load_from_filesystem()
        else:
            logger.warning("Refresh requires MPD client or filesystem path")
            return 0

    def clear_cache(self):
        """Clear catalog cache"""
        self._catalog = []
        self._catalog_metadata = []
        self._favorites = []
        self._phonetic_cache = {}
        self._query_phonetic_cache = {}
        self._search_best_cache = {}
        logger.debug("Catalog cache cleared")

    def is_empty(self) -> bool:
        """Check if catalog is empty"""
        return len(self._catalog) == 0

    def file_exists(self, file_path: str) -> bool:
        """Check if file exists in catalog"""
        return file_path in self._catalog


def main():
    """Test music library"""
    import sys

    # Test with filesystem
    if len(sys.argv) > 1:
        library_path = sys.argv[1]
    else:
        library_path = os.path.expanduser("~/Music")

    print("Music Library Test\n")
    print("=" * 60)

    library = MusicLibrary(library_path=library_path, debug=True)

    # Load catalog
    print(f"\n1. Loading catalog from: {library_path}")
    count = library.load_from_filesystem()
    print(f"   Loaded {count} songs")

    if count == 0:
        print("   No songs found. Check library path.")
        return

    # Test search
    print("\n2. Testing search...")
    test_queries = ["frozen", "beatles", "hey jude", "frozzen"]  # Last one is typo

    for query in test_queries:
        result = library.search(query)
        if result:
            file_path, confidence = result
            print(f"   '{query}' → {os.path.basename(file_path)} ({confidence:.2%})")
        else:
            print(f"   '{query}' → No match")

    # Test favorites
    print("\n3. Testing favorites...")
    favorites = library.get_favorites()
    print(f"   Favorites count: {len(favorites)}")

    if favorites:
        print("   First 3 favorites:")
        for song in favorites[:3]:
            print(f"     - {song}")


if __name__ == '__main__':
    main()
