"""
Protocol Interfaces for Pi-Sat Modules

Defines contracts for all major modules, enabling:
- Easy swapping of implementations
- Clear documentation of module responsibilities
- Type checking and IDE support
- Dependency injection patterns

Following KISS principle: Simple interfaces, no complex abstractions.
"""

from typing import Protocol, Optional, Tuple, List, Dict, Any
from dataclasses import dataclass


@dataclass
class Intent:
    """Structured intent representation"""
    intent_type: str  # Intent category (play_music, volume_up, etc.)
    confidence: float  # Match confidence (0.0 - 1.0)
    parameters: Dict  # Extracted parameters (song_name, duration, etc.)
    raw_text: str  # Original transcribed text
    language: str = 'fr'  # Language of the intent (added for DDD compliance)

    def __repr__(self) -> str:
        params = ""
        if self.parameters:
            parts = [f"{k}={v}" for k, v in self.parameters.items()]
            params = ", " + ", ".join(parts)
        return (
            f"Intent(intent_type={self.intent_type!r}, confidence={self.confidence:.2f}"
            f"{params}, raw_text={self.raw_text!r}, language={self.language!r})"
        )


@dataclass
class ValidationResult:
    """
    Value Object for command validation results.

    Immutable result containing validation outcome and user feedback in target language.
    """
    is_valid: bool
    feedback_message: str  # TTS message to speak to user
    validated_params: Dict[str, Any]  # Validated/normalized parameters
    confidence: float = 1.0


class STTEngine(Protocol):
    """Speech-to-Text Engine Interface"""

    def transcribe(self, audio_data: bytes) -> str:
        """
        Transcribe audio to text.

        Args:
            audio_data: Audio bytes (16kHz, mono, PCM)

        Returns:
            Transcribed text or empty string on failure
        """
        ...

    def is_available(self) -> bool:
        """Check if STT engine is available"""
        ...

    def reload(self) -> None:
        """Reload STT model"""
        ...

    def cleanup(self) -> None:
        """Clean up resources"""
        ...


class TTSEngine(Protocol):
    """Text-to-Speech Engine Interface"""

    def speak(self, text: str, volume: Optional[int] = None) -> bool:
        """
        Generate and play speech.

        Args:
            text: Text to speak
            volume: Optional volume (0-100)

        Returns:
            True if successful
        """
        ...

    def generate_audio(self, text: str, output_path: Optional[str] = None) -> Optional[bytes]:
        """
        Generate speech audio.

        Args:
            text: Text to generate
            output_path: Optional file path to save

        Returns:
            Audio bytes if output_path is None, else True/False
        """
        ...

    def get_response_template(self, intent: str, **params) -> str:
        """Get pre-defined response for intent"""
        ...


class IntentClassifier(Protocol):
    """Intent Classification Engine Interface"""

    def classify(self, text: str) -> Optional[Intent]:
        """
        Classify text into structured intent.

        Args:
            text: Transcribed voice command

        Returns:
            Intent object or None if no match
        """
        ...

    def get_supported_intents(self) -> List[str]:
        """Get list of supported intent types"""
        ...


class MusicCatalog(Protocol):
    """Music Library Catalog Interface"""

    def search(self, query: str) -> Optional[Tuple[str, float]]:
        """
        Search catalog for best match.

        Args:
            query: Search query

        Returns:
            Tuple of (file_path, confidence) or None
        """
        ...

    def get_all_songs(self) -> List[str]:
        """Get all songs in catalog"""
        ...

    def get_favorites(self) -> List[str]:
        """Get favorites playlist"""
        ...

    def add_to_favorites(self, song_path: str) -> bool:
        """Add song to favorites"""
        ...

    def refresh(self) -> None:
        """Refresh catalog from music library"""
        ...


class MusicPlayer(Protocol):
    """Music Playback Control Interface"""

    def play(self, query: Optional[str] = None) -> Tuple[bool, str, Optional[float]]:
        """Play music (with optional search query, returns confidence)"""
        ...

    def pause(self) -> Tuple[bool, str]:
        """Pause playback"""
        ...

    def resume(self) -> Tuple[bool, str]:
        """Resume playback"""
        ...

    def stop(self) -> Tuple[bool, str]:
        """Stop playback"""
        ...

    def next(self) -> Tuple[bool, str]:
        """Next track"""
        ...

    def previous(self) -> Tuple[bool, str]:
        """Previous track"""
        ...

    def volume_up(self, amount: int = 10) -> Tuple[bool, str]:
        """Increase volume"""
        ...

    def volume_down(self, amount: int = 10) -> Tuple[bool, str]:
        """Decrease volume"""
        ...

    def get_status(self) -> Dict:
        """Get player status"""
        ...

    def play_favorites(self) -> Tuple[bool, str]:
        """Play favorites playlist"""
        ...

    def add_to_favorites(self) -> Tuple[bool, str]:
        """Add current song to favorites"""
        ...

    def set_sleep_timer(self, minutes: int) -> Tuple[bool, str]:
        """Set sleep timer"""
        ...

    def set_repeat(self, mode: str) -> Tuple[bool, str]:
        """Set repeat mode ('off', 'single', 'playlist')"""
        ...

    def set_shuffle(self, enabled: bool) -> Tuple[bool, str]:
        """Set shuffle mode"""
        ...

    def toggle_shuffle(self) -> Tuple[bool, str]:
        """Toggle shuffle mode on/off"""
        ...

    def add_to_queue(self, query: str, play_next: bool = False) -> Tuple[bool, str]:
        """Add song to queue (optionally as next song)"""
        ...

    def clear_queue(self) -> Tuple[bool, str]:
        """Clear the current queue/playlist"""
        ...

    def get_queue(self) -> List[Dict]:
        """Get current queue/playlist"""
        ...

    def get_queue_length(self) -> int:
        """Get number of songs in queue"""
        ...


class VolumeControl(Protocol):
    """Volume Management Interface"""

    def get_music_volume(self) -> Optional[int]:
        """Get music volume (0-100)"""
        ...

    def set_music_volume(self, volume: int) -> bool:
        """Set music volume (0-100)"""
        ...

    def music_volume_up(self, amount: int = 10) -> Tuple[bool, str]:
        """Increase music volume"""
        ...

    def music_volume_down(self, amount: int = 10) -> Tuple[bool, str]:
        """Decrease music volume"""
        ...


class SpeechRecognition(Protocol):
    """Speech Recording Interface"""

    def record_command(self) -> bytes:
        """
        Record voice command using VAD.

        Returns:
            Audio bytes (PCM format)
        """
        ...

    def process_audio_chunks(self, audio: bytes, sample_rate: int) -> bytes:
        """Process audio chunks with VAD"""
        ...


class WakeWordDetector(Protocol):
    """Wake Word Detection Interface"""

    def start_listening(self) -> None:
        """Start listening for wake word"""
        ...

    def stop_listening(self) -> None:
        """Stop listening"""
        ...

    def detect_wake_word(self, audio_data: bytes) -> bool:
        """Detect wake word in audio (for testing)"""
        ...


class TimeScheduling(Protocol):
    """Time-based Scheduling Interface (Bedtime enforcement)"""

    def is_quiet_time(self) -> bool:
        """Check if current time is during quiet hours (bedtime)"""
        ...

    def is_playback_allowed(self) -> Tuple[bool, Optional[str]]:
        """
        Check if music playback is currently allowed.

        Returns:
            Tuple of (allowed, reason_if_not_allowed)
        """
        ...

    def minutes_until_quiet_time(self) -> Optional[int]:
        """
        Calculate minutes until quiet time starts.

        Returns:
            Minutes until bedtime, or None if already in quiet time
        """
        ...

    def should_warn_about_bedtime(self) -> Tuple[bool, Optional[int]]:
        """
        Check if we should warn about approaching bedtime.

        Returns:
            Tuple of (should_warn, minutes_remaining)
        """
        ...

    def get_schedule_info(self) -> str:
        """Get human-readable schedule information"""
        ...

    def update_schedule(self, start_time: Optional[str] = None, end_time: Optional[str] = None) -> str:
        """Update bedtime schedule"""
        ...


class AlarmManagement(Protocol):
    """Morning Alarm Management Interface"""

    def set_alarm(
        self,
        wake_time: str,
        music_query: Optional[str] = None,
        gentle_wakeup: bool = True,
        recurring: str = 'once'
    ) -> Tuple[bool, str]:
        """
        Set a new alarm.

        Args:
            wake_time: Wake time in HH:MM format
            music_query: Music to play (None for favorites)
            gentle_wakeup: Enable gentle volume fade-in
            recurring: 'once', 'daily', 'weekdays', 'weekends'

        Returns:
            Tuple of (success, message)
        """
        ...

    def cancel_alarm(self, alarm_id: Optional[int] = None) -> Tuple[bool, str]:
        """Cancel alarm(s)"""
        ...

    def check_and_trigger(self) -> bool:
        """
        Check if any alarms should trigger.

        Returns:
            True if an alarm was triggered
        """
        ...


class UsageTracking(Protocol):
    """Activity Tracking Interface (Daily time limits)"""

    def start_tracking(self) -> bool:
        """
        Start tracking current session.

        Returns:
            True if tracking started, False if limit already reached
        """
        ...

    def stop_tracking(self) -> None:
        """Stop tracking current session"""
        ...

    def pause_tracking(self) -> None:
        """Pause tracking (e.g., when music is paused)"""
        ...

    def resume_tracking(self) -> None:
        """Resume tracking (e.g., when music is resumed)"""
        ...

    def is_limit_reached(self) -> bool:
        """Check if daily time limit has been reached"""
        ...

    def get_remaining_minutes(self) -> Optional[int]:
        """
        Get remaining listening time for today.

        Returns:
            Minutes remaining, or None if limits disabled
        """
        ...

    def get_used_minutes(self) -> int:
        """Get total listening time used today"""
        ...

    def should_warn_about_limit(self) -> Tuple[bool, Optional[int]]:
        """
        Check if we should warn about approaching time limit.

        Returns:
            Tuple of (should_warn, minutes_remaining)
        """
        ...

    def get_usage_summary(self) -> str:
        """Get human-readable usage summary"""
        ...


class CommandValidation(Protocol):
    """Command Validation Interface (Domain Service)"""

    def validate(self, intent: Intent) -> ValidationResult:
        """
        Validate command before execution and provide user feedback.

        Args:
            intent: Classified intent to validate

        Returns:
            ValidationResult with validation outcome and TTS feedback message
        """
        ...


# Type aliases for convenience
CommandResult = Tuple[bool, str]  # (success, message)
SearchResult = Optional[Tuple[str, float]]  # (file_path, confidence)
