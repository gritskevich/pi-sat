"""
Command Validator - Domain Service for Command Validation

DDD Domain Service that validates commands before execution and provides
smart TTS feedback in French.

Architecture:
- Domain Service (not tied to infrastructure)
- Returns ValidationResult value object
- Separates validation logic from execution logic
- Provides rich French feedback for users
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from modules.interfaces import Intent
from modules.logging_utils import setup_logger

logger = setup_logger(__name__)


@dataclass
class ValidationResult:
    """
    Value Object representing validation outcome.

    Immutable result of command validation with rich feedback.
    """
    is_valid: bool
    feedback_message: str  # French TTS message to speak
    validated_params: Dict[str, Any]  # Validated/normalized parameters
    confidence: float = 1.0

    @staticmethod
    def valid(message: str, params: Dict[str, Any], confidence: float = 1.0) -> 'ValidationResult':
        """Create valid result."""
        return ValidationResult(
            is_valid=True,
            feedback_message=message,
            validated_params=params,
            confidence=confidence
        )

    @staticmethod
    def invalid(message: str) -> 'ValidationResult':
        """Create invalid result."""
        return ValidationResult(
            is_valid=False,
            feedback_message=message,
            validated_params={},
            confidence=0.0
        )


class CommandValidator:
    """
    Domain Service for command validation.

    Validates commands before execution and provides smart French feedback.
    Follows DDD principles:
    - Domain logic separate from infrastructure
    - Rich domain language (French responses)
    - Value objects for results
    """

    def __init__(self, music_library=None, language: str = 'fr', debug: bool = False):
        """
        Initialize command validator.

        Args:
            music_library: MusicLibrary instance for catalog validation
            language: Response language ('fr' or 'en')
            debug: Enable debug logging
        """
        self.music_library = music_library
        self.language = language
        self.debug = debug
        self.logger = setup_logger(__name__, debug=debug)

        # French validation messages
        self._messages_fr = {
            # Play music validation
            'playing_song': "D'accord, je joue {song}",
            'playing_artist': "D'accord, je joue {artist}",
            'playing_with_confidence': "Je pense que tu veux écouter {song}",
            'no_music_found': "Désolé, je n'ai pas trouvé {query} dans ta bibliothèque",
            'empty_library': "Ta bibliothèque musicale est vide",

            # Simple controls validation
            'pausing': "D'accord, je mets en pause",
            'resuming': "Je reprends la musique",
            'stopping': "D'accord, j'arrête",
            'next_song': "Chanson suivante",
            'previous_song': "Chanson précédente",

            # Volume validation
            'volume_up': "J'augmente le volume",
            'volume_down': "Je baisse le volume",
            'set_volume': "Je mets le volume à {volume}%",
            'volume_too_high': "Le volume maximum est {max_volume}%, je mets à {volume}%",
            'invalid_volume': "Désolé, je n'ai pas compris le niveau de volume",

            # Favorites validation
            'adding_favorite': "D'accord, j'ajoute aux favoris",
            'playing_favorites': "Je joue tes favoris",

            # Sleep timer validation
            'sleep_timer': "D'accord, j'arrête dans {minutes} minutes",
            'invalid_duration': "Désolé, je n'ai pas compris la durée",

            # Repeat/Shuffle validation
            'repeat_on': "D'accord, je répète",
            'repeat_off': "D'accord, j'arrête de répéter",
            'shuffle_on': "D'accord, je mélange",
            'shuffle_off': "D'accord, j'arrête de mélanger",

            # Queue validation
            'play_next': "D'accord, {song} sera joué ensuite",
            'add_to_queue': "D'accord, j'ajoute {song} à la file",

            # Alarm validation
            'alarm_set': "D'accord, alarme à {time}",
            'alarm_cancelled': "Alarme annulée",
            'invalid_time': "Désolé, je n'ai pas compris l'heure",

            # Errors
            'unknown_command': "Désolé, je n'ai pas compris",
            'validation_error': "Désolé, il y a un problème",
        }

        # English validation messages
        self._messages_en = {
            'playing_song': "Okay, playing {song}",
            'playing_artist': "Okay, playing {artist}",
            'playing_with_confidence': "I think you want to listen to {song}",
            'no_music_found': "Sorry, I couldn't find {query} in your library",
            'empty_library': "Your music library is empty",
            'pausing': "Okay, pausing",
            'resuming': "Resuming music",
            'stopping': "Okay, stopping",
            'next_song': "Next song",
            'previous_song': "Previous song",
            'volume_up': "Volume up",
            'volume_down': "Volume down",
            'set_volume': "Setting volume to {volume}%",
            'volume_too_high': "Maximum volume is {max_volume}%, setting to {volume}%",
            'invalid_volume': "Sorry, I didn't understand the volume level",
            'adding_favorite': "Okay, adding to favorites",
            'playing_favorites': "Playing your favorites",
            'sleep_timer': "Okay, I'll stop in {minutes} minutes",
            'invalid_duration': "Sorry, I didn't understand the duration",
            'repeat_on': "Okay, repeating",
            'repeat_off': "Okay, stopping repeat",
            'shuffle_on': "Okay, shuffling",
            'shuffle_off': "Okay, stopping shuffle",
            'play_next': "Okay, {song} will play next",
            'add_to_queue': "Okay, adding {song} to queue",
            'alarm_set': "Okay, alarm at {time}",
            'alarm_cancelled': "Alarm cancelled",
            'invalid_time': "Sorry, I didn't understand the time",
            'unknown_command': "Sorry, I didn't understand",
            'validation_error': "Sorry, something went wrong",
        }

    def _get_message(self, key: str, **params) -> str:
        """Get message in current language with parameters."""
        messages = self._messages_fr if self.language == 'fr' else self._messages_en
        template = messages.get(key, messages['unknown_command'])
        try:
            return template.format(**params)
        except KeyError:
            return template

    def validate(self, intent: Intent) -> ValidationResult:
        """
        Validate command and return result with French feedback.

        Args:
            intent: Classified intent to validate

        Returns:
            ValidationResult with validation outcome and TTS feedback
        """
        try:
            intent_type = intent.intent_type
            params = intent.parameters or {}

            # Play music validation - most complex
            if intent_type == 'play_music':
                return self._validate_play_music(params)

            # Simple controls - always valid
            elif intent_type in ['pause', 'resume', 'stop', 'next', 'previous']:
                return self._validate_simple_control(intent_type)

            # Volume controls - always valid
            elif intent_type in ['volume_up', 'volume_down']:
                return self._validate_volume(intent_type)

            # Set volume - validate level
            elif intent_type == 'set_volume':
                return self._validate_set_volume(params)

            # Favorites
            elif intent_type in ['add_favorite', 'play_favorites']:
                return self._validate_favorites(intent_type)

            # Sleep timer
            elif intent_type == 'sleep_timer':
                return self._validate_sleep_timer(params)

            # Repeat/Shuffle
            elif intent_type in ['repeat_song', 'repeat_off', 'shuffle_on', 'shuffle_off']:
                return self._validate_repeat_shuffle(intent_type)

            # Queue management
            elif intent_type in ['play_next', 'add_to_queue']:
                return self._validate_queue(intent_type, params)

            # Alarms
            elif intent_type in ['set_alarm', 'cancel_alarm']:
                return self._validate_alarm(intent_type, params)

            # Other intents - pass through as valid
            else:
                # Bedtime, time limits, etc. - infrastructure concerns, not domain
                return ValidationResult.valid(
                    message=self._get_message('unknown_command'),
                    params=params
                )

        except Exception as e:
            self.logger.error(f"Validation error: {e}")
            return ValidationResult.invalid(
                message=self._get_message('validation_error')
            )

    def _validate_play_music(self, params: Dict[str, Any]) -> ValidationResult:
        """Validate play music command with catalog check."""
        query = params.get('query', '').strip()

        if not query:
            return ValidationResult.invalid(
                message=self._get_message('unknown_command')
            )

        # Check if music library available
        if not self.music_library:
            # No validation possible, optimistic response
            return ValidationResult.valid(
                message=self._get_message('playing_song', song=query),
                params={'query': query},
                confidence=0.7
            )

        # Check if library has songs
        if self.music_library.is_empty():
            return ValidationResult.invalid(
                message=self._get_message('empty_library')
            )

        # Search for song/artist in catalog
        result = self.music_library.search(query)

        if not result:
            return ValidationResult.invalid(
                message=self._get_message('no_music_found', query=query)
            )

        # Got match - MusicLibrary.search returns (file_path, confidence)
        best_match, confidence = result

        # High confidence - confirm what we found
        if confidence >= 0.8:
            return ValidationResult.valid(
                message=self._get_message('playing_song', song=best_match),
                params={'query': best_match},
                confidence=confidence
            )
        else:
            # Lower confidence - express uncertainty
            return ValidationResult.valid(
                message=self._get_message('playing_with_confidence', song=best_match),
                params={'query': best_match},
                confidence=confidence
            )

    def _validate_simple_control(self, intent_type: str) -> ValidationResult:
        """Validate simple playback controls."""
        message_keys = {
            'pause': 'pausing',
            'resume': 'resuming',
            'stop': 'stopping',
            'next': 'next_song',
            'previous': 'previous_song'
        }
        return ValidationResult.valid(
            message=self._get_message(message_keys[intent_type]),
            params={}
        )

    def _validate_volume(self, intent_type: str) -> ValidationResult:
        """Validate volume controls."""
        return ValidationResult.valid(
            message=self._get_message(intent_type),
            params={}
        )

    def _validate_set_volume(self, params: Dict[str, Any]) -> ValidationResult:
        """Validate set volume command with safety limits."""
        import config

        volume = params.get('volume')

        if volume is None or not isinstance(volume, (int, float)):
            return ValidationResult.invalid(
                message=self._get_message('invalid_volume')
            )

        # Ensure volume is integer
        volume = int(volume)

        # Check if volume exceeds safety limit
        max_volume = getattr(config, 'MAX_VOLUME', 100)
        if volume > max_volume:
            return ValidationResult.valid(
                message=self._get_message('volume_too_high', max_volume=max_volume, volume=max_volume),
                params={'volume': max_volume},
                confidence=1.0
            )

        # Valid volume
        return ValidationResult.valid(
            message=self._get_message('set_volume', volume=volume),
            params={'volume': volume},
            confidence=1.0
        )

    def _validate_favorites(self, intent_type: str) -> ValidationResult:
        """Validate favorites commands."""
        message_keys = {
            'add_favorite': 'adding_favorite',
            'play_favorites': 'playing_favorites'
        }
        return ValidationResult.valid(
            message=self._get_message(message_keys[intent_type]),
            params={}
        )

    def _validate_sleep_timer(self, params: Dict[str, Any]) -> ValidationResult:
        """Validate sleep timer command."""
        duration = params.get('duration_minutes')

        if not duration or not isinstance(duration, (int, float)) or duration <= 0:
            return ValidationResult.invalid(
                message=self._get_message('invalid_duration')
            )

        return ValidationResult.valid(
            message=self._get_message('sleep_timer', minutes=int(duration)),
            params={'duration_minutes': int(duration)}
        )

    def _validate_repeat_shuffle(self, intent_type: str) -> ValidationResult:
        """Validate repeat/shuffle commands."""
        message_keys = {
            'repeat_song': 'repeat_on',
            'repeat_off': 'repeat_off',
            'shuffle_on': 'shuffle_on',
            'shuffle_off': 'shuffle_off'
        }
        return ValidationResult.valid(
            message=self._get_message(message_keys[intent_type]),
            params={}
        )

    def _validate_queue(self, intent_type: str, params: Dict[str, Any]) -> ValidationResult:
        """Validate queue management commands."""
        query = params.get('query', '').strip()

        if not query:
            return ValidationResult.invalid(
                message=self._get_message('unknown_command')
            )

        message_keys = {
            'play_next': 'play_next',
            'add_to_queue': 'add_to_queue'
        }

        return ValidationResult.valid(
            message=self._get_message(message_keys[intent_type], song=query),
            params={'query': query}
        )

    def _validate_alarm(self, intent_type: str, params: Dict[str, Any]) -> ValidationResult:
        """Validate alarm commands."""
        if intent_type == 'cancel_alarm':
            return ValidationResult.valid(
                message=self._get_message('alarm_cancelled'),
                params={}
            )

        # set_alarm
        time_str = params.get('time', '').strip()

        if not time_str:
            return ValidationResult.invalid(
                message=self._get_message('invalid_time')
            )

        return ValidationResult.valid(
            message=self._get_message('alarm_set', time=time_str),
            params={'time': time_str}
        )
