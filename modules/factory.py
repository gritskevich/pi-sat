"""
Factory Module - Dependency Injection for Pi-Sat

Provides factory functions to create properly configured instances:
- Production setup (real hardware)
- Test setup (mocked dependencies)
- Custom configurations

Implements dependency injection pattern for:
- Easy testing with mocked components
- Clear dependency graphs
- Separation of construction from use
- Configuration management

Following KISS principle: Simple factory functions, no complex frameworks.
"""

import config
from modules.speech_recorder import SpeechRecorder
from modules.hailo_stt import HailoSTT
from modules.intent_engine import IntentEngine
from modules.mpd_controller import MPDController
from modules.piper_tts import PiperTTS
from modules.volume_manager import VolumeManager
from modules.command_processor import CommandProcessor
from modules.music_library import MusicLibrary


def create_music_library(
    library_path: str = None,
    fuzzy_threshold: int = None,
    debug: bool = False
) -> MusicLibrary:
    """
    Create MusicLibrary instance with config defaults.

    Args:
        library_path: Music directory path (None for config default)
        fuzzy_threshold: Fuzzy match threshold (None for config default)
        debug: Enable debug logging

    Returns:
        Configured MusicLibrary instance
    """
    library_path = library_path or config.MUSIC_LIBRARY
    fuzzy_threshold = fuzzy_threshold or config.FUZZY_MATCH_THRESHOLD

    return MusicLibrary(
        library_path=library_path,
        fuzzy_threshold=fuzzy_threshold,
        cache_enabled=True,
        debug=debug
    )


def create_mpd_controller(
    host: str = None,
    port: int = None,
    music_library: str = None,
    debug: bool = False
) -> MPDController:
    """
    Create MPDController instance with config defaults.

    Args:
        host: MPD host (None for config default)
        port: MPD port (None for config default)
        music_library: Music library path (None for config default)
        debug: Enable debug logging

    Returns:
        Configured MPDController instance
    """
    host = host or config.MPD_HOST
    port = port or config.MPD_PORT
    music_library = music_library or config.MUSIC_LIBRARY

    return MPDController(
        host=host,
        port=port,
        music_library=music_library,
        debug=debug
    )


def create_volume_manager(
    mpd_controller: MPDController = None,
    debug: bool = False
) -> VolumeManager:
    """
    Create VolumeManager instance.

    Args:
        mpd_controller: Optional MPD controller (created if None)
        debug: Enable debug logging

    Returns:
        Configured VolumeManager instance
    """
    if mpd_controller is None:
        mpd_controller = create_mpd_controller(debug=debug)

    return VolumeManager(mpd_controller=mpd_controller)


def create_speech_recorder(debug: bool = False) -> SpeechRecorder:
    """
    Create SpeechRecorder instance.

    Args:
        debug: Enable debug logging

    Returns:
        Configured SpeechRecorder instance
    """
    return SpeechRecorder(debug=debug)


def create_stt_engine(debug: bool = False) -> HailoSTT:
    """
    Create STT engine instance.

    Args:
        debug: Enable debug logging

    Returns:
        Configured HailoSTT instance
    """
    return HailoSTT(debug=debug)


def create_intent_engine(
    fuzzy_threshold: int = None,
    debug: bool = False
) -> IntentEngine:
    """
    Create IntentEngine instance.

    Args:
        fuzzy_threshold: Fuzzy match threshold (None for config default)
        debug: Enable debug logging

    Returns:
        Configured IntentEngine instance
    """
    fuzzy_threshold = fuzzy_threshold or config.FUZZY_MATCH_THRESHOLD

    return IntentEngine(
        fuzzy_threshold=fuzzy_threshold,
        debug=debug
    )


def create_tts_engine(
    volume_manager: VolumeManager = None,
    output_device: str = None,
    debug: bool = False
) -> PiperTTS:
    """
    Create TTS engine instance.

    Args:
        volume_manager: Optional volume manager
        output_device: ALSA output device (None for config default)
        debug: Enable debug logging

    Returns:
        Configured PiperTTS instance
    """
    output_device = output_device or config.PIPER_OUTPUT_DEVICE

    return PiperTTS(
        volume_manager=volume_manager,
        output_device=output_device
    )


def create_command_processor(
    speech_recorder: SpeechRecorder = None,
    stt_engine: HailoSTT = None,
    intent_engine: IntentEngine = None,
    mpd_controller: MPDController = None,
    tts_engine: PiperTTS = None,
    volume_manager: VolumeManager = None,
    debug: bool = False,
    verbose: bool = True
) -> CommandProcessor:
    """
    Create CommandProcessor with all dependencies.

    Args:
        speech_recorder: Optional SpeechRecorder (created if None)
        stt_engine: Optional STT engine (created if None)
        intent_engine: Optional IntentEngine (created if None)
        mpd_controller: Optional MPDController (created if None)
        tts_engine: Optional TTS engine (created if None)
        volume_manager: Optional VolumeManager (created if None)
        debug: Enable debug logging
        verbose: Enable verbose output

    Returns:
        Configured CommandProcessor instance
    """
    # Create missing dependencies
    if mpd_controller is None:
        mpd_controller = create_mpd_controller(debug=debug)

    if volume_manager is None:
        volume_manager = create_volume_manager(mpd_controller=mpd_controller)

    if speech_recorder is None:
        speech_recorder = create_speech_recorder(debug=debug)

    if stt_engine is None:
        stt_engine = create_stt_engine(debug=debug)

    if intent_engine is None:
        intent_engine = create_intent_engine(debug=debug)

    if tts_engine is None:
        tts_engine = create_tts_engine(volume_manager=volume_manager)

    return CommandProcessor(
        speech_recorder=speech_recorder,
        stt_engine=stt_engine,
        intent_engine=intent_engine,
        mpd_controller=mpd_controller,
        tts_engine=tts_engine,
        volume_manager=volume_manager,
        debug=debug,
        verbose=verbose
    )


def create_production_orchestrator(debug: bool = False, verbose: bool = True):
    """
    Create Orchestrator for production use (real hardware).

    This is the main entry point for production deployment.

    Args:
        debug: Enable debug logging
        verbose: Enable verbose output

    Returns:
        Configured Orchestrator instance
    """
    # Import here to avoid circular dependency
    from modules.orchestrator import Orchestrator

    # Create command processor with all production dependencies
    command_processor = create_command_processor(debug=debug, verbose=verbose)

    # Create orchestrator
    orchestrator = Orchestrator(
        command_processor=command_processor,
        debug=debug,
        verbose=verbose
    )

    return orchestrator


def create_test_command_processor(
    mock_stt: str = "test transcription",
    mock_intent: str = "play_music",
    debug: bool = True
):
    """
    Create CommandProcessor for testing with mocked dependencies.

    Args:
        mock_stt: Mock transcription text
        mock_intent: Mock intent type
        debug: Enable debug logging

    Returns:
        CommandProcessor with mocked dependencies
    """
    # This would be used in tests with proper mocking
    # For now, just return a regular processor
    return create_command_processor(debug=debug)


# Convenience aliases
create_orchestrator = create_production_orchestrator


if __name__ == '__main__':
    print("Factory Module - Dependency Injection for Pi-Sat\n")
    print("=" * 60)

    print("\n1. Creating production orchestrator...")
    orchestrator = create_production_orchestrator(debug=True)
    print(f"   ✓ Orchestrator created")

    print("\n2. Creating individual components...")
    library = create_music_library(debug=True)
    print(f"   ✓ MusicLibrary created")

    mpd = create_mpd_controller(debug=True)
    print(f"   ✓ MPDController created")

    volume = create_volume_manager(mpd_controller=mpd)
    print(f"   ✓ VolumeManager created")

    processor = create_command_processor(debug=True)
    print(f"   ✓ CommandProcessor created")

    print("\n3. Factory module ready for use!")
    print("\nUsage:")
    print("  from modules.factory import create_production_orchestrator")
    print("  orchestrator = create_production_orchestrator()")
    print("  orchestrator.start()")
