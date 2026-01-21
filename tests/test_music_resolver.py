"""
Tests for MusicResolver - Query Extraction + Catalog Resolution

Validates music query extraction from natural language and catalog matching.
"""

import pytest
from pathlib import Path

from modules.music_resolver import MusicResolver, MusicResolution
from modules.music_library import MusicLibrary
from tests.utils.fixture_loader import load_fixture


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "music_resolver_cases.json"


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
    def test_extract_query_french(self, resolver):
        fixture = load_fixture(FIXTURE_PATH)
        for case in fixture["extract_fr"]:
            query = resolver.extract_query(case["text"], language="fr")
            if "query_contains" in case:
                assert case["query_contains"] in query.lower()
            else:
                assert query == case["query"]

    def test_extract_query_english(self, resolver):
        fixture = load_fixture(FIXTURE_PATH)
        for case in fixture["extract_en"]:
            query = resolver.extract_query(case["text"], language="en")
            assert query == case["query"]

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
    def test_clean_query(self, resolver):
        fixture = load_fixture(FIXTURE_PATH)
        for case in fixture["clean_queries"]:
            query = resolver._clean_query(case["text"], language="fr")
            assert query == case["query"]

    # Integration with Real Library
    def test_resolve_real_library(self):
        """Test resolution with real music library."""
        library = MusicLibrary(debug=False)
        resolver = MusicResolver(library)

        # Test with any query - should extract it even if no match
        result = resolver.resolve("joue maman", language="fr")
        # Should extract query even if no match
        assert result.query in ["maman", "joue maman"]
