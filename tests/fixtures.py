"""Shared test fixtures for Pi-Sat tests

Provides pre-configured mocks for common test components to reduce duplication.
Following DRY principle - extracted from ~44 test setUp methods.

Usage:
    from tests.fixtures import create_mock_intent_engine, create_mock_mpd_controller

    def setUp(self):
        self.mock_intent = create_mock_intent_engine(language='fr')
        self.mock_mpd = create_mock_mpd_controller()
"""

import config
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock
from modules.intent_patterns import Intent


def create_mock_intent_engine(language='fr', fuzzy_threshold=None):
    """
    Create a pre-configured mock IntentEngine.

    Args:
        language: Language code ('fr' or 'en')
        fuzzy_threshold: Fuzzy match threshold (default: config.FUZZY_MATCH_THRESHOLD)

    Returns:
        Mock IntentEngine with standard configuration

    Example:
        >>> engine = create_mock_intent_engine(language='fr', fuzzy_threshold=50)
        >>> engine.classify("joue frozen")
        Intent(intent_type='play_music', confidence=0.95, ...)
    """
    threshold = fuzzy_threshold if fuzzy_threshold is not None else config.FUZZY_MATCH_THRESHOLD

    engine = Mock()
    engine.language = language
    engine.fuzzy_threshold = threshold
    engine.classify.return_value = Intent(
        intent_type='play_music',
        confidence=0.95,
        parameters={'song': 'test song'},
        matched_pattern='joue {song}'
    )
    return engine


def create_mock_mpd_controller():
    """
    Create a pre-configured mock MPDController.

    Returns:
        Mock MPDController with standard status/song responses

    Example:
        >>> mpd = create_mock_mpd_controller()
        >>> mpd.client.status()
        {'state': 'play', 'playlistlength': '10', ...}
    """
    mpd = Mock()
    mpd.client = Mock()
    mpd._ensure_connection = MagicMock(return_value=Mock(__enter__=Mock(), __exit__=Mock()))

    mpd.client.status.return_value = {
        'state': 'play',
        'playlistlength': '10',
        'song': '3',
        'volume': '100'
    }

    mpd.client.currentsong.return_value = {
        'file': 'test.mp3',
        'artist': 'Test Artist',
        'title': 'Test Song'
    }

    responses = json.loads(
        Path(__file__).resolve().parent.parent.joinpath("resources/response_library.json").read_text(encoding="utf-8")
    )

    def pick(lang, key, **params):
        return responses.get(lang, {}).get(key, [""])[0].format(**params)

    mpd.play.return_value = (True, pick('fr', 'playing_song', song="test song"))
    mpd.pause.return_value = (True, pick('fr', 'paused'))
    mpd.resume.return_value = (True, pick('fr', 'resuming'))
    mpd.stop.return_value = (True, pick('fr', 'stopped'))
    mpd.next.return_value = (True, pick('fr', 'next_song'))
    mpd.previous.return_value = (True, pick('fr', 'previous_song'))

    return mpd


def create_mock_speech_recorder():
    """
    Create a pre-configured mock SpeechRecorder.

    Returns:
        Mock SpeechRecorder with dummy audio data

    Example:
        >>> recorder = create_mock_speech_recorder()
        >>> audio = recorder.record_command()
        >>> len(audio)
        2000
    """
    recorder = Mock()
    # Dummy audio data (1000 int16 samples = 2000 bytes)
    recorder.record_command.return_value = b'\x00\x01' * 1000
    recorder.record_from_stream.return_value = b'\x00\x01' * 1000
    return recorder


def create_mock_stt_engine(transcription="test transcription"):
    """
    Create a pre-configured mock STT engine.

    Args:
        transcription: Text to return from transcribe() calls

    Returns:
        Mock STT engine

    Example:
        >>> stt = create_mock_stt_engine(transcription="alexa joue frozen")
        >>> stt.transcribe(audio_data)
        'alexa joue frozen'
    """
    stt = Mock()
    stt.transcribe.return_value = transcription
    stt.is_available.return_value = True
    return stt


def create_mock_tts_engine():
    """
    Create a pre-configured mock TTS engine.

    Returns:
        Mock TTS engine

    Example:
        >>> tts = create_mock_tts_engine()
        >>> tts.speak("Hello")
        True
    """
    tts = Mock()
    tts.speak.return_value = True
    return tts


def create_mock_volume_manager(current_volume=50):
    """
    Create a pre-configured mock VolumeManager.

    Args:
        current_volume: Initial volume level (0-100)

    Returns:
        Mock VolumeManager

    Example:
        >>> vol = create_mock_volume_manager(current_volume=50)
        >>> vol.get_volume()
        50
    """
    volume_mgr = Mock()
    volume_mgr.get_volume.return_value = current_volume
    volume_mgr.set_volume.return_value = True
    volume_mgr.volume_up.return_value = min(100, current_volume + 5)
    volume_mgr.volume_down.return_value = max(0, current_volume - 5)
    return volume_mgr


def create_mock_command_validator():
    """
    Create a pre-configured mock CommandValidator.

    Returns:
        Mock CommandValidator that validates all commands

    Example:
        >>> validator = create_mock_command_validator()
        >>> validator.validate(intent)
        (True, {'validated': True})
    """
    validator = Mock()
    validator.validate.return_value = (True, {'validated': True})
    return validator
