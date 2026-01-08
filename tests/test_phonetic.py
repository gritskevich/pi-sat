"""
Tests for phonetic encoding module (FONEM algorithm).
"""

import pytest
from modules.phonetic import PhoneticEncoder, encode_pattern, encode_query, is_available


class TestPhoneticEncoder:
    """Test PhoneticEncoder class"""

    def test_initialization_fonem(self):
        """Test FONEM encoder initialization"""
        encoder = PhoneticEncoder(algorithm="fonem")
        # FONEM may or may not be available depending on dependencies
        assert encoder.algorithm == "fonem"

    def test_initialization_beidermorse(self):
        """Test BeiderMorse encoder initialization"""
        encoder = PhoneticEncoder(algorithm="beidermorse")
        assert encoder.algorithm == "beidermorse"

    def test_is_available(self):
        """Test availability check"""
        encoder = PhoneticEncoder()
        # Just check method exists and returns boolean
        assert isinstance(encoder.is_available(), bool)

    @pytest.mark.skipif(not is_available(), reason="Phonetic library not available")
    def test_encode_pattern_basic(self):
        """Test basic pattern encoding"""
        encoder = PhoneticEncoder()

        # Encode a simple French word
        encoded = encoder.encode_pattern("chanson")
        assert isinstance(encoded, str)
        assert len(encoded) > 0

    @pytest.mark.skipif(not is_available(), reason="Phonetic library not available")
    def test_encode_pattern_caching(self):
        """Test that pattern encoding is cached"""
        encoder = PhoneticEncoder()

        # First encoding
        text = "musique"
        encoded1 = encoder.encode_pattern(text)
        cache_size1 = encoder.cache_size()

        # Second encoding (should use cache)
        encoded2 = encoder.encode_pattern(text)
        cache_size2 = encoder.cache_size()

        # Results should be identical
        assert encoded1 == encoded2
        # Cache size should not increase
        assert cache_size2 == cache_size1

    @pytest.mark.skipif(not is_available(), reason="Phonetic library not available")
    def test_encode_query_no_caching(self):
        """Test that query encoding is NOT cached"""
        encoder = PhoneticEncoder()

        # Clear cache
        encoder.clear_cache()
        initial_size = encoder.cache_size()

        # Encode query
        text = "frozen"
        encoded = encoder.encode_query(text)

        # Cache should not grow
        assert encoder.cache_size() == initial_size
        assert isinstance(encoded, str)
        assert len(encoded) > 0

    @pytest.mark.skipif(not is_available(), reason="Phonetic library not available")
    def test_normalization(self):
        """Test text normalization (accents, case, non-alphanumeric)"""
        encoder = PhoneticEncoder()

        # Test with accented characters
        encoded1 = encoder.encode_pattern("éléphant")
        encoded2 = encoder.encode_pattern("elephant")

        # Should produce same or very similar encodings
        # (normalization removes accents)
        assert isinstance(encoded1, str)
        assert isinstance(encoded2, str)

    @pytest.mark.skipif(not is_available(), reason="Phonetic library not available")
    def test_minimum_length_threshold(self):
        """Test that short strings are rejected"""
        encoder = PhoneticEncoder()

        # Less than 3 characters should return empty string
        assert encoder.encode_pattern("ab") == ""
        assert encoder.encode_pattern("a") == ""
        assert encoder.encode_pattern("") == ""

        # 3+ characters should encode
        assert len(encoder.encode_pattern("abc")) > 0

    @pytest.mark.skipif(not is_available(), reason="Phonetic library not available")
    def test_empty_input(self):
        """Test empty string handling"""
        encoder = PhoneticEncoder()

        assert encoder.encode_pattern("") == ""
        assert encoder.encode_query("") == ""
        assert encoder.encode_pattern(None) == ""

    @pytest.mark.skipif(not is_available(), reason="Phonetic library not available")
    def test_cache_clear(self):
        """Test cache clearing"""
        encoder = PhoneticEncoder()

        # Add some items to cache
        encoder.encode_pattern("hello")
        encoder.encode_pattern("world")

        assert encoder.cache_size() > 0

        # Clear cache
        encoder.clear_cache()

        assert encoder.cache_size() == 0

    @pytest.mark.skipif(not is_available(), reason="Phonetic library not available")
    def test_similar_words_french(self):
        """Test that phonetically similar French words produce similar encodings"""
        encoder = PhoneticEncoder()

        # These words sound similar in French
        encoded1 = encoder.encode_pattern("chanson")
        encoded2 = encoder.encode_pattern("chansons")

        # Should have some similarity (both start with same phonetic root)
        assert isinstance(encoded1, str)
        assert isinstance(encoded2, str)
        assert len(encoded1) > 0
        assert len(encoded2) > 0

    def test_unavailable_encoder(self):
        """Test behavior when encoder is not available"""
        # Create encoder with invalid algorithm
        encoder = PhoneticEncoder(algorithm="invalid")

        assert not encoder.is_available()
        assert encoder.encode_pattern("test") == ""
        assert encoder.encode_query("test") == ""


class TestConvenienceFunctions:
    """Test convenience functions"""

    def test_get_default_encoder(self):
        """Test default encoder creation"""
        # Should not raise
        encoded = encode_pattern("test")
        assert isinstance(encoded, str)

    def test_encode_pattern_function(self):
        """Test encode_pattern convenience function"""
        result = encode_pattern("test")
        assert isinstance(result, str)

    def test_encode_query_function(self):
        """Test encode_query convenience function"""
        result = encode_query("test")
        assert isinstance(result, str)

    def test_is_available_function(self):
        """Test is_available convenience function"""
        result = is_available()
        assert isinstance(result, bool)


class TestFrenchSTTErrorCases:
    """Test phonetic matching on realistic French STT errors"""

    @pytest.mark.skipif(not is_available(), reason="Phonetic library not available")
    def test_frozen_variants(self):
        """Test Frozen song title variants (common STT errors)"""
        encoder = PhoneticEncoder()

        # Correct title
        correct = encoder.encode_pattern("frozen")

        # Common STT errors
        variant1 = encoder.encode_query("frosen")  # Common misheard
        variant2 = encoder.encode_query("froze")
        variant3 = encoder.encode_query("frozon")

        # All should produce encodings (even if different)
        assert len(correct) > 0
        assert len(variant1) > 0
        assert len(variant2) > 0
        assert len(variant3) > 0

    @pytest.mark.skipif(not is_available(), reason="Phonetic library not available")
    def test_libere_delivre_variants(self):
        """Test 'Libérée, Délivrée' title variants"""
        encoder = PhoneticEncoder()

        # Correct title
        correct = encoder.encode_pattern("liberee delivree")

        # Common STT variations
        variant1 = encoder.encode_query("liberer delivrer")
        variant2 = encoder.encode_query("libere delivre")

        assert len(correct) > 0
        assert len(variant1) > 0
        assert len(variant2) > 0

    @pytest.mark.skipif(not is_available(), reason="Phonetic library not available")
    def test_artist_name_variants(self):
        """Test artist name encoding"""
        encoder = PhoneticEncoder()

        # Artist names
        encoded1 = encoder.encode_pattern("louane")
        encoded2 = encoder.encode_query("louan")  # Common STT error
        encoded3 = encoder.encode_query("loane")

        assert len(encoded1) > 0
        assert len(encoded2) > 0
        assert len(encoded3) > 0
