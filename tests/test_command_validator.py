"""
Tests for CommandValidator - Domain Service for Command Validation

Tests validation logic with French TTS feedback messages.
"""

import json
from pathlib import Path
import pytest
from modules.command_validator import CommandValidator, ValidationResult
from modules.interfaces import Intent
from modules.music_library import MusicLibrary
from tests.utils.fixture_loader import load_fixture

RESPONSE_LIBRARY = json.loads(
    Path(__file__).resolve().parent.parent.joinpath("resources/response_library.json").read_text(encoding="utf-8")
)
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "command_validator_fr.json"


def _response_options(language: str, key: str, **params):
    options = RESPONSE_LIBRARY.get(language, {}).get(key, [])
    return [template.format(**params) for template in options]


class TestValidationResult:
    """Test ValidationResult value object."""

    def test_valid_result(self):
        """Test creating valid result."""
        message = RESPONSE_LIBRARY["fr"]["unknown"][0]
        result = ValidationResult.valid(
            message=message,
            params={'query': 'test'},
            confidence=0.9
        )
        assert result.is_valid is True
        assert result.feedback_message == message
        assert result.validated_params == {'query': 'test'}
        assert result.confidence == 0.9

    def test_invalid_result(self):
        """Test creating invalid result."""
        message = RESPONSE_LIBRARY["fr"]["unknown"][1]
        result = ValidationResult.invalid(message=message)
        assert result.is_valid is False
        assert result.feedback_message == message
        assert result.validated_params == {}
        assert result.confidence == 0.0


class TestCommandValidatorFrench:
    """Test CommandValidator with French messages."""

    @pytest.fixture
    def music_library(self):
        """Music library with test songs."""
        library = MusicLibrary(debug=True)
        return library

    @pytest.fixture
    def validator_fr(self, music_library):
        """French validator with music library."""
        return CommandValidator(music_library=music_library, language='fr')

    # Play music validation tests
    def test_play_music_valid_high_confidence(self, validator_fr, monkeypatch):
        """Test play music with high confidence match."""
        # Mock library methods
        def mock_is_empty():
            return False
        def mock_search_best(query):
            return ("Frozen.mp3", 0.9)

        monkeypatch.setattr(validator_fr.music_library, 'is_empty', mock_is_empty)
        monkeypatch.setattr(validator_fr.music_library, 'search_best', mock_search_best)

        intent = Intent(
            intent_type='play_music',
            confidence=0.9,
            parameters={'query': 'frozen'},
            raw_text='joue frozen',
            language='fr'
        )

        result = validator_fr.validate(intent)

        # Should validate successfully with high confidence
        assert result.is_valid is True
        assert result.feedback_message in _response_options('fr', 'playing_song', song="Frozen")
        assert result.confidence >= 0.8

    def test_play_music_valid_low_confidence(self, validator_fr, monkeypatch):
        """Test play music with low confidence match."""
        # Mock library methods
        def mock_is_empty():
            return False
        def mock_search_best(query):
            return ("test_song.mp3", 0.6)

        monkeypatch.setattr(validator_fr.music_library, 'is_empty', mock_is_empty)
        monkeypatch.setattr(validator_fr.music_library, 'search_best', mock_search_best)

        intent = Intent(
            intent_type='play_music',
            confidence=0.9,
            parameters={'query': 'xyz'},
            raw_text='joue xyz',
            language='fr'
        )

        result = validator_fr.validate(intent)

        # Should validate with uncertainty message
        assert result.is_valid is True
        assert result.feedback_message in _response_options('fr', 'playing_with_confidence', song="test_song")
        assert result.confidence < 0.8

    def test_play_music_no_match(self, validator_fr, monkeypatch):
        """Test play music with no catalog match - or very low confidence."""
        # Mock library methods
        def mock_is_empty():
            return False
        def mock_search_best(query):
            # Return low confidence match (<50%) to trigger rejection
            return ("test_song.mp3", 0.3)

        monkeypatch.setattr(validator_fr.music_library, 'is_empty', mock_is_empty)
        monkeypatch.setattr(validator_fr.music_library, 'search_best', mock_search_best)

        intent = Intent(
            intent_type='play_music',
            confidence=0.9,
            parameters={'query': 'nonexistent'},
            raw_text='joue nonexistent',
            language='fr'
        )

        result = validator_fr.validate(intent)

        # Should fail validation
        assert result.is_valid is False
        assert result.feedback_message in _response_options('fr', 'no_music_found', query='nonexistent')

    def test_play_music_empty_query(self, validator_fr):
        """Test play music with empty query."""
        intent = Intent(
            intent_type='play_music',
            confidence=0.9,
            parameters={'query': ''},
            raw_text='joue',
            language='fr'
        )

        result = validator_fr.validate(intent)

        # Should fail validation
        assert result.is_valid is False

    def test_play_music_empty_library(self, validator_fr, monkeypatch):
        """Test play music with empty library."""
        # Mock empty library
        def mock_is_empty():
            return True
        monkeypatch.setattr(validator_fr.music_library, 'is_empty', mock_is_empty)

        intent = Intent(
            intent_type='play_music',
            confidence=0.9,
            parameters={'query': 'frozen'},
            raw_text='joue frozen',
            language='fr'
        )

        result = validator_fr.validate(intent)

        # Should fail validation
        assert result.is_valid is False
        assert result.feedback_message in _response_options('fr', 'empty_library')

    # Simple control validation tests
    def test_simple_control_validation(self, validator_fr):
        """Test simple control commands."""
        fixture = load_fixture(FIXTURE_PATH)
        for case in fixture["simple_controls"]:
            intent = Intent(
                intent_type=case["intent"],
                confidence=0.9,
                parameters={},
                raw_text=case["raw_text"],
                language="fr"
            )
            result = validator_fr.validate(intent)
            assert result.is_valid is True
            assert result.feedback_message in _response_options('fr', case["response_key"])

    # Volume validation tests
    def test_volume_validation(self, validator_fr):
        """Test volume up/down validation."""
        fixture = load_fixture(FIXTURE_PATH)
        for case in fixture["volume_controls"]:
            intent = Intent(
                intent_type=case["intent"],
                confidence=0.9,
                parameters={},
                raw_text=case["raw_text"],
                language="fr"
            )
            result = validator_fr.validate(intent)
            assert result.is_valid is True
            assert result.feedback_message in _response_options('fr', case["response_key"])

class TestCommandValidatorEnglish:
    """Test CommandValidator with English messages."""

    @pytest.fixture
    def validator_en(self):
        """English validator without music library."""
        return CommandValidator(music_library=None, language='en')

    def test_play_music_no_library_en(self, validator_en):
        """Test play music without library in English."""
        intent = Intent(
            intent_type='play_music',
            confidence=0.9,
            parameters={'query': 'frozen'},
            raw_text='play frozen',
            language='en'
        )

        result = validator_en.validate(intent)

        # Should succeed optimistically (no library to validate against)
        assert result.is_valid is True
        assert result.feedback_message in _response_options('en', 'playing_song', song='frozen')
        assert result.confidence == 0.7  # Lower confidence without validation

    def test_volume_up_en(self, validator_en):
        """Test volume up in English."""
        intent = Intent(
            intent_type='volume_up',
            confidence=0.9,
            parameters={},
            raw_text='louder',
            language='en'
        )

        result = validator_en.validate(intent)

        assert result.is_valid is True
        assert result.feedback_message in _response_options('en', 'volume_up')


class TestCommandValidatorErrorHandling:
    """Test error handling in CommandValidator."""

    @pytest.fixture
    def validator_fr(self):
        """French validator without music library."""
        return CommandValidator(music_library=None, language='fr')

    def test_unknown_intent(self, validator_fr):
        """Test validation of unknown intent type."""
        intent = Intent(
            intent_type='unknown_intent',
            confidence=0.9,
            parameters={},
            raw_text='fais quelque chose',
            language='fr'
        )

        result = validator_fr.validate(intent)

        # Should pass through as valid (infrastructure concerns, not domain)
        assert result.is_valid is True

    def test_validation_exception_handling(self, validator_fr, monkeypatch):
        """Test validation handles exceptions gracefully."""
        # Force an exception in _validate_simple_control
        def mock_validate_simple(*args):
            raise Exception("Test exception")
        monkeypatch.setattr(validator_fr, '_validate_simple_control', mock_validate_simple)

        intent = Intent(
            intent_type='pause',
            confidence=0.9,
            parameters={},
            raw_text='stop',
            language='fr'
        )

        result = validator_fr.validate(intent)

        # Should return error result with error message
        assert result.is_valid is False
        assert result.feedback_message in _response_options('fr', 'validation_error')
