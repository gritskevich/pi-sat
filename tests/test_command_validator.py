"""
Tests for CommandValidator - Domain Service for Command Validation

Tests validation logic with French TTS feedback messages.
"""

import pytest
from modules.command_validator import CommandValidator, ValidationResult
from modules.interfaces import Intent
from modules.music_library import MusicLibrary


class TestValidationResult:
    """Test ValidationResult value object."""

    def test_valid_result(self):
        """Test creating valid result."""
        result = ValidationResult.valid(
            message="D'accord",
            params={'query': 'test'},
            confidence=0.9
        )
        assert result.is_valid is True
        assert result.feedback_message == "D'accord"
        assert result.validated_params == {'query': 'test'}
        assert result.confidence == 0.9

    def test_invalid_result(self):
        """Test creating invalid result."""
        result = ValidationResult.invalid(message="Désolé")
        assert result.is_valid is False
        assert result.feedback_message == "Désolé"
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
        def mock_search(query):
            return [("Frozen.mp3", 0.9)]

        monkeypatch.setattr(validator_fr.music_library, 'is_empty', mock_is_empty)
        monkeypatch.setattr(validator_fr.music_library, 'search', mock_search)

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
        assert 'accord' in result.feedback_message.lower()
        assert result.confidence >= 0.8

    def test_play_music_valid_low_confidence(self, validator_fr, monkeypatch):
        """Test play music with low confidence match."""
        # Mock library methods
        def mock_is_empty():
            return False
        def mock_search(query):
            return [("test_song.mp3", 0.6)]

        monkeypatch.setattr(validator_fr.music_library, 'is_empty', mock_is_empty)
        monkeypatch.setattr(validator_fr.music_library, 'search', mock_search)

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
        assert 'pense' in result.feedback_message.lower() or 'sûr' in result.feedback_message.lower()
        assert result.confidence < 0.8

    def test_play_music_no_match(self, validator_fr, monkeypatch):
        """Test play music with no catalog match."""
        # Mock library methods
        def mock_is_empty():
            return False
        def mock_search(query):
            return []

        monkeypatch.setattr(validator_fr.music_library, 'is_empty', mock_is_empty)
        monkeypatch.setattr(validator_fr.music_library, 'search', mock_search)

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
        assert 'pas trouvé' in result.feedback_message.lower()
        assert 'nonexistent' in result.feedback_message

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
        assert 'vide' in result.feedback_message.lower()

    # Simple control validation tests
    def test_pause_validation(self, validator_fr):
        """Test pause command validation."""
        intent = Intent(
            intent_type='pause',
            confidence=0.9,
            parameters={},
            raw_text='pause',
            language='fr'
        )

        result = validator_fr.validate(intent)

        assert result.is_valid is True
        assert 'pause' in result.feedback_message.lower()

    def test_resume_validation(self, validator_fr):
        """Test resume command validation."""
        intent = Intent(
            intent_type='resume',
            confidence=0.9,
            parameters={},
            raw_text='reprends',
            language='fr'
        )

        result = validator_fr.validate(intent)

        assert result.is_valid is True
        assert 'reprends' in result.feedback_message.lower() or 'musique' in result.feedback_message.lower()

    def test_stop_validation(self, validator_fr):
        """Test stop command validation."""
        intent = Intent(
            intent_type='stop',
            confidence=0.9,
            parameters={},
            raw_text='arrête',
            language='fr'
        )

        result = validator_fr.validate(intent)

        assert result.is_valid is True
        assert 'arrête' in result.feedback_message.lower()

    def test_next_validation(self, validator_fr):
        """Test next command validation."""
        intent = Intent(
            intent_type='next',
            confidence=0.9,
            parameters={},
            raw_text='suivant',
            language='fr'
        )

        result = validator_fr.validate(intent)

        assert result.is_valid is True
        assert 'suivant' in result.feedback_message.lower()

    def test_previous_validation(self, validator_fr):
        """Test previous command validation."""
        intent = Intent(
            intent_type='previous',
            confidence=0.9,
            parameters={},
            raw_text='précédent',
            language='fr'
        )

        result = validator_fr.validate(intent)

        assert result.is_valid is True
        assert 'précédent' in result.feedback_message.lower()

    # Volume validation tests
    def test_volume_up_validation(self, validator_fr):
        """Test volume up validation."""
        intent = Intent(
            intent_type='volume_up',
            confidence=0.9,
            parameters={},
            raw_text='plus fort',
            language='fr'
        )

        result = validator_fr.validate(intent)

        assert result.is_valid is True
        assert 'volume' in result.feedback_message.lower()

    def test_volume_down_validation(self, validator_fr):
        """Test volume down validation."""
        intent = Intent(
            intent_type='volume_down',
            confidence=0.9,
            parameters={},
            raw_text='moins fort',
            language='fr'
        )

        result = validator_fr.validate(intent)

        assert result.is_valid is True
        assert 'volume' in result.feedback_message.lower()

    # Favorites validation tests
    def test_add_favorite_validation(self, validator_fr):
        """Test add to favorites validation."""
        intent = Intent(
            intent_type='add_favorite',
            confidence=0.9,
            parameters={},
            raw_text='j\'aime',
            language='fr'
        )

        result = validator_fr.validate(intent)

        assert result.is_valid is True
        assert 'favoris' in result.feedback_message.lower()

    def test_play_favorites_validation(self, validator_fr):
        """Test play favorites validation."""
        intent = Intent(
            intent_type='play_favorites',
            confidence=0.9,
            parameters={},
            raw_text='joue mes favoris',
            language='fr'
        )

        result = validator_fr.validate(intent)

        assert result.is_valid is True
        assert 'favoris' in result.feedback_message.lower()

    # Sleep timer validation tests
    def test_sleep_timer_valid(self, validator_fr):
        """Test sleep timer with valid duration."""
        intent = Intent(
            intent_type='sleep_timer',
            confidence=0.9,
            parameters={'duration_minutes': 30},
            raw_text='arrête dans 30 minutes',
            language='fr'
        )

        result = validator_fr.validate(intent)

        assert result.is_valid is True
        assert '30' in result.feedback_message
        assert 'minutes' in result.feedback_message.lower()

    def test_sleep_timer_invalid_duration(self, validator_fr):
        """Test sleep timer with invalid duration."""
        intent = Intent(
            intent_type='sleep_timer',
            confidence=0.9,
            parameters={'duration_minutes': None},
            raw_text='arrête dans un moment',
            language='fr'
        )

        result = validator_fr.validate(intent)

        assert result.is_valid is False
        assert 'compris' in result.feedback_message.lower()

    def test_sleep_timer_negative_duration(self, validator_fr):
        """Test sleep timer with negative duration."""
        intent = Intent(
            intent_type='sleep_timer',
            confidence=0.9,
            parameters={'duration_minutes': -5},
            raw_text='arrête dans -5 minutes',
            language='fr'
        )

        result = validator_fr.validate(intent)

        assert result.is_valid is False

    # Repeat/Shuffle validation tests
    def test_repeat_on_validation(self, validator_fr):
        """Test repeat on validation."""
        intent = Intent(
            intent_type='repeat_song',
            confidence=0.9,
            parameters={},
            raw_text='répète',
            language='fr'
        )

        result = validator_fr.validate(intent)

        assert result.is_valid is True
        assert 'répète' in result.feedback_message.lower()

    def test_shuffle_on_validation(self, validator_fr):
        """Test shuffle on validation."""
        intent = Intent(
            intent_type='shuffle_on',
            confidence=0.9,
            parameters={},
            raw_text='mélange',
            language='fr'
        )

        result = validator_fr.validate(intent)

        assert result.is_valid is True
        assert 'mélange' in result.feedback_message.lower()

    # Queue validation tests
    def test_play_next_validation(self, validator_fr):
        """Test play next validation."""
        intent = Intent(
            intent_type='play_next',
            confidence=0.9,
            parameters={'query': 'frozen'},
            raw_text='joue frozen ensuite',
            language='fr'
        )

        result = validator_fr.validate(intent)

        assert result.is_valid is True
        assert 'ensuite' in result.feedback_message.lower()
        assert 'frozen' in result.feedback_message.lower()

    def test_play_next_empty_query(self, validator_fr):
        """Test play next with empty query."""
        intent = Intent(
            intent_type='play_next',
            confidence=0.9,
            parameters={'query': ''},
            raw_text='joue ensuite',
            language='fr'
        )

        result = validator_fr.validate(intent)

        assert result.is_valid is False

    # Alarm validation tests
    def test_set_alarm_valid(self, validator_fr):
        """Test set alarm with valid time."""
        intent = Intent(
            intent_type='set_alarm',
            confidence=0.9,
            parameters={'time': '07:00'},
            raw_text='réveille-moi à 7 heures',
            language='fr'
        )

        result = validator_fr.validate(intent)

        assert result.is_valid is True
        assert '07:00' in result.feedback_message
        assert 'alarme' in result.feedback_message.lower()

    def test_set_alarm_invalid_time(self, validator_fr):
        """Test set alarm with invalid time."""
        intent = Intent(
            intent_type='set_alarm',
            confidence=0.9,
            parameters={'time': ''},
            raw_text='réveille-moi',
            language='fr'
        )

        result = validator_fr.validate(intent)

        assert result.is_valid is False
        assert 'compris' in result.feedback_message.lower()

    def test_cancel_alarm_validation(self, validator_fr):
        """Test cancel alarm validation."""
        intent = Intent(
            intent_type='cancel_alarm',
            confidence=0.9,
            parameters={},
            raw_text='annule l\'alarme',
            language='fr'
        )

        result = validator_fr.validate(intent)

        assert result.is_valid is True
        assert 'alarme' in result.feedback_message.lower()


class TestCommandValidatorEnglish:
    """Test CommandValidator with English messages."""

    @pytest.fixture
    def validator_en(self):
        """English validator without music library."""
        return CommandValidator(music_library=None, language='en')

    def test_pause_validation_en(self, validator_en):
        """Test pause command validation in English."""
        intent = Intent(
            intent_type='pause',
            confidence=0.9,
            parameters={},
            raw_text='pause',
            language='en'
        )

        result = validator_en.validate(intent)

        assert result.is_valid is True
        assert 'paus' in result.feedback_message.lower()

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
        assert 'frozen' in result.feedback_message.lower()
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
        assert 'volume' in result.feedback_message.lower()


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
            raw_text='pause',
            language='fr'
        )

        result = validator_fr.validate(intent)

        # Should return error result with error message
        assert result.is_valid is False
        assert 'problème' in result.feedback_message.lower() or 'error' in result.feedback_message.lower()
