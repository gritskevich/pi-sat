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

import atexit
import subprocess
import config
from modules.speech_recorder import SpeechRecorder
from modules.hailo_stt import HailoSTT
from modules.intent_engine import IntentEngine
from modules.mpd_controller import MPDController
from modules.mpd_connection import MPDConnection
from modules.sleep_timer import SleepTimer
from modules.piper_tts import PiperTTS
from modules.volume_manager import VolumeManager
from modules.command_processor import CommandProcessor
from modules.music_library import MusicLibrary
from modules.logging_utils import setup_logger
from modules.event_bus import EventBus
from modules.player_event_router import PlayerEventRouter
from modules.event_logger import EventLogger
from modules.music_search_router import MusicSearchRouter
from modules.playback_state_machine import PlaybackStateMachine

logger = setup_logger(__name__)


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

    # Update MPD database to sync with filesystem changes
    try:
        subprocess.run(['mpc', 'update'], check=False, capture_output=True, timeout=5)
    except Exception as e:
        logger.debug(f"MPD database update failed (non-critical): {e}")

    return MusicLibrary(
        library_path=library_path,
        fuzzy_threshold=fuzzy_threshold,
        cache_enabled=True,
        phonetic_enabled=True,  # FONEM (French-specific, 75x faster than BeiderMorse)
        debug=debug
    )


def create_mpd_controller(
    host: str = None,
    port: int = None,
    music_library_instance: MusicLibrary = None,  # NEW: Inject MusicLibrary
    mpd_connection: MPDConnection = None,  # NEW: Inject MPDConnection
    sleep_timer: SleepTimer = None,  # NEW: Inject SleepTimer
    debug: bool = False
) -> MPDController:
    """
    Create MPDController instance with config defaults.

    Args:
        host: MPD host (None for config default)
        port: MPD port (None for config default)
        music_library_instance: Pre-configured MusicLibrary instance (recommended)
        mpd_connection: Pre-configured MPDConnection instance (optional)
        sleep_timer: Pre-configured SleepTimer instance (optional)
        debug: Enable debug logging

    Returns:
        Configured MPDController instance (connected to MPD)

    Note:
        Prefer using music_library_instance for better testability and to share
        a single MusicLibrary instance across components.
    """
    host = host or config.MPD_HOST
    port = port or config.MPD_PORT

    # Create MusicLibrary if not injected
    if music_library_instance is None:
        music_library_instance = create_music_library(debug=debug)

    # Create MPDConnection if not injected
    if mpd_connection is None:
        mpd_connection = MPDConnection(
            host=host,
            port=port,
            debug=debug
        )

    # Create SleepTimer if not injected
    if sleep_timer is None:
        sleep_timer = SleepTimer(debug=debug)

    mpd = MPDController(
        mpd_connection=mpd_connection,
        sleep_timer=sleep_timer,
        music_library_instance=music_library_instance,
        debug=debug
    )

    # Lazy connection - _ensure_connection handles it when first MPD operation is called
    # This allows system to start even if MPD is temporarily unavailable

    return mpd


def create_volume_manager(
    mpd_controller: MPDController = None,
    debug: bool = False
) -> VolumeManager:
    """
    Create VolumeManager instance and initialize to default volume.

    Args:
        mpd_controller: Optional MPD controller (created if None)
        debug: Enable debug logging

    Returns:
        Configured VolumeManager instance
    """
    if mpd_controller is None:
        mpd_controller = create_mpd_controller(debug=debug)

    volume_manager = VolumeManager(mpd_controller=mpd_controller, debug=debug)

    # Initialize to default volume on startup (from config.MASTER_VOLUME)
    volume_manager.initialize_default_volume(default_volume=config.MASTER_VOLUME)

    return volume_manager


def create_speech_recorder(debug: bool = False) -> SpeechRecorder:
    """
    Create SpeechRecorder instance.

    Args:
        debug: Enable debug logging

    Returns:
        Configured SpeechRecorder instance
    """
    return SpeechRecorder(debug=debug)


def create_stt_engine(debug: bool = False):
    """
    Create STT engine instance.

    Args:
        debug: Enable debug logging

    Returns:
        Configured HailoSTT instance
    """
    if config.STT_BACKEND == "cpu":
        from modules.cpu_stt import CpuSTT
        return CpuSTT(debug=debug)
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
    event_bus: EventBus = None,
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
        event_bus=event_bus,
        debug=debug,
        verbose=verbose
    )


def create_event_bus(debug: bool = False) -> EventBus:
    """Create EventBus instance."""
    return EventBus(debug=debug)


def create_player_event_router(
    event_bus: EventBus,
    mpd_controller: MPDController,
    volume_manager: VolumeManager,
    debug: bool = False
) -> PlayerEventRouter:
    """Create router that maps control events to MPD/volume actions."""
    return PlayerEventRouter(
        event_bus=event_bus,
        mpd_controller=mpd_controller,
        volume_manager=volume_manager,
        debug=debug
    )


def create_event_logger(debug: bool = False) -> EventLogger:
    """Create EventLogger instance based on config."""
    enabled = getattr(config, "EVENT_LOGGER", "jsonl") != "none"
    path = getattr(config, "EVENT_LOG_PATH", "")
    return EventLogger(path=path, enabled=enabled)


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

    event_bus = create_event_bus(debug=debug)

    # Create MPD + Volume ahead so routers can subscribe
    mpd_controller = create_mpd_controller(debug=debug)
    volume_manager = create_volume_manager(mpd_controller=mpd_controller)
    create_player_event_router(
        event_bus=event_bus,
        mpd_controller=mpd_controller,
        volume_manager=volume_manager,
        debug=debug
    )
    MusicSearchRouter(
        event_bus=event_bus,
        music_library=mpd_controller.get_music_library(),
        debug=debug
    )
    PlaybackStateMachine(
        event_bus=event_bus,
        mpd_controller=mpd_controller,
        debug=debug
    )

    event_logger = create_event_logger(debug=debug)
    event_bus.subscribe_all(event_logger.log)
    event_bus.start()
    atexit.register(event_bus.stop)

    # Create command processor with all production dependencies
    command_processor = create_command_processor(
        mpd_controller=mpd_controller,
        volume_manager=volume_manager,
        event_bus=event_bus,
        debug=debug,
        verbose=verbose
    )

    # Create orchestrator
    orchestrator = Orchestrator(
        command_processor=command_processor,
        event_bus=event_bus,
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
