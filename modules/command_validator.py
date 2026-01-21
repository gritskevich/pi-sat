from dataclasses import dataclass
from typing import Optional, Dict, Any
from modules.interfaces import Intent
from modules.logging_utils import setup_logger
from modules.response_library import ResponseLibrary

logger = setup_logger(__name__)


@dataclass
class ValidationResult:
    is_valid: bool
    feedback_message: str  # French TTS message to speak
    validated_params: Dict[str, Any]  # Validated/normalized parameters
    confidence: float = 1.0

    @staticmethod
    def valid(message: str, params: Dict[str, Any], confidence: float = 1.0) -> 'ValidationResult':
        return ValidationResult(
            is_valid=True,
            feedback_message=message,
            validated_params=params,
            confidence=confidence
        )

    @staticmethod
    def invalid(message: str) -> 'ValidationResult':
        return ValidationResult(
            is_valid=False,
            feedback_message=message,
            validated_params={},
            confidence=0.0
        )


class CommandValidator:
    def __init__(self, music_library=None, language: str = 'fr', debug: bool = False):
        self.music_library = music_library
        self.language = language
        self.debug = debug
        self.logger = setup_logger(__name__, debug=debug)
        self._responses = ResponseLibrary(language=language)

    def _get_message(self, key: str, **params) -> str:
        response = self._responses.get(key, fallback_key="unknown_command", **params)
        if response:
            return response
        self.logger.warning(f"Missing response template for '{key}'")
        return ""

    def validate(self, intent: Intent) -> ValidationResult:
        try:
            intent_type = intent.intent_type
            params = intent.parameters or {}

            # Play music validation - most complex
            if intent_type == 'play_music':
                return self._validate_play_music(params)

            # Simple controls - always valid
            elif intent_type in ['pause', 'resume', 'continue', 'next', 'previous']:
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
        # Use search_best() to always return something for play_music intent
        # Better to play low-confidence match than nothing
        result = self.music_library.search_best(query)

        if not result:
            # Should never happen with search_best() unless library is empty
            return ValidationResult.invalid(
                message=self._get_message('no_music_found', query=query)
            )

        # Got match - MusicLibrary.search_best returns (file_path, confidence)
        best_match, confidence = result

        # Strip .mp3 extension for cleaner TTS
        import os
        song_name = os.path.splitext(best_match)[0]

        # Reject very low confidence matches (likely wrong song)
        if confidence < 0.4:
            return ValidationResult.invalid(
                message=self._get_message('no_music_found', query=query)
            )

        # High confidence (>=80%) - confirm what we found
        if confidence >= 0.8:
            return ValidationResult.valid(
                message=self._get_message('playing_song', song=song_name),
                params={'matched_file': best_match, 'query': query},
                confidence=confidence
            )
        # Medium confidence (50-80%) - express uncertainty
        else:
            return ValidationResult.valid(
                message=self._get_message('playing_with_confidence', song=song_name),
                params={'matched_file': best_match, 'query': query},
                confidence=confidence
            )

    def _validate_simple_control(self, intent_type: str) -> ValidationResult:
        """Validate simple playback controls."""
        message_keys = {
            'pause': 'pausing',
            'resume': 'resuming',
            'continue': 'resuming',
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
