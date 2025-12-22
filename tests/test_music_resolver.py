"""
Tests for MusicResolver - Query Extraction + Catalog Resolution

Validates music query extraction from natural language and catalog matching.
"""

import pytest
from modules.music_resolver import MusicResolver, MusicResolution
from modules.music_library import MusicLibrary


class TestMusicResolver:
    """Test MusicResolver query extraction and catalog matching."""

    @pytest.fixture
    def library(self):
        """Create test music library."""
        library = MusicLibrary(debug=False)
        return library

    @pytest.fixture
    def resolver(self, library):
        """Create music resolver with test library."""
        return MusicResolver(library)

    # Query Extraction Tests - French
    def test_extract_query_french_basic(self, resolver):
        """Test basic French query extraction: 'joue maman'."""
        query = resolver.extract_query("joue maman", language="fr")
        assert query == "maman"

    def test_extract_query_french_mets(self, resolver):
        """Test French 'mets' command."""
        query = resolver.extract_query("mets frozen", language="fr")
        assert query == "frozen"

    def test_extract_query_french_je_veux(self, resolver):
        """Test French 'je veux écouter' command."""
        query = resolver.extract_query("je veux écouter la reine des neiges", language="fr")
        assert query == "la reine des neiges"

    def test_extract_query_french_long_phrase(self, resolver):
        """Test French query with 'de' separator."""
        query = resolver.extract_query("joue la musique de la reine des neiges", language="fr")
        # Should extract artist after 'de'
        assert "la reine des neiges" in query.lower()

    def test_extract_query_french_empty(self, resolver):
        """Test empty query."""
        query = resolver.extract_query("", language="fr")
        assert query == ""

    def test_extract_query_french_no_trigger(self, resolver):
        """Test French text without trigger words."""
        query = resolver.extract_query("la reine des neiges", language="fr")
        # Fallback returns empty string when no trigger words found
        assert query == ""

    # Query Extraction Tests - English
    def test_extract_query_english_play(self, resolver):
        """Test English 'play' command."""
        query = resolver.extract_query("play frozen", language="en")
        assert query == "frozen"

    def test_extract_query_english_listen_to(self, resolver):
        """Test English 'listen to' command."""
        query = resolver.extract_query("listen to the frozen soundtrack", language="en")
        assert query == "the frozen soundtrack"

    # Resolution Tests
    def test_resolve_with_explicit_query(self, resolver, monkeypatch):
        """Test resolution with explicit query parameter."""
        # Mock library search
        def mock_search(query):
            return ("frozen.mp3", 0.95)
        monkeypatch.setattr(resolver.library, 'search_best', mock_search)

        result = resolver.resolve("joue frozen", language="fr", explicit_query="frozen")
        assert result.query == "frozen"
        assert result.matched_file == "frozen.mp3"
        assert result.confidence == 0.95

    def test_resolve_extracts_query(self, resolver, monkeypatch):
        """Test resolution extracts query from text."""
        # Mock library search
        def mock_search(query):
            return ("frozen.mp3", 0.85)
        monkeypatch.setattr(resolver.library, 'search_best', mock_search)

        result = resolver.resolve("joue frozen", language="fr")
        assert result.query == "frozen"
        assert result.matched_file == "frozen.mp3"

    def test_resolve_no_match(self, resolver, monkeypatch):
        """Test resolution when no catalog match found."""
        # Mock library search - no match
        def mock_search(query):
            return None
        monkeypatch.setattr(resolver.library, 'search_best', mock_search)

        result = resolver.resolve("joue nonexistent", language="fr")
        assert result.query == "nonexistent"
        assert result.matched_file is None
        assert result.confidence is None

    def test_resolve_empty_query(self, resolver):
        """Test resolution with empty query."""
        result = resolver.resolve("", language="fr")
        assert result.query == ""
        assert result.matched_file is None

    # Query Cleaning Tests
    def test_clean_query_strips_punctuation(self, resolver):
        """Test query cleaning removes punctuation."""
        query = resolver._clean_query("frozen!!!", language="fr")
        assert query == "frozen"

    def test_clean_query_normalizes_spaces(self, resolver):
        """Test query cleaning normalizes whitespace."""
        query = resolver._clean_query("la   reine   des   neiges", language="fr")
        assert query == "la reine des neiges"

    # Integration with Real Library
    def test_resolve_real_library(self):
        """Test resolution with real music library."""
        library = MusicLibrary(debug=False)
        resolver = MusicResolver(library)

        # Test with any query - should extract it even if no match
        result = resolver.resolve("joue maman", language="fr")
        # Should extract query even if no match
        assert result.query in ["maman", "joue maman"]
