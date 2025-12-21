"""
Orchestrator - Application Lifecycle Manager

Manages Pi-Sat application lifecycle:
- Wake word detection
- Command processing delegation
- Signal handling
- Graceful shutdown

Refactored for clarity and testability:
- Delegates command processing to CommandProcessor
- Focuses on lifecycle management only
- Supports dependency injection for testing

Following KISS principle: Simple lifecycle, delegate complexity.
"""

import subprocess
import time
import threading
import signal
import sys
import os
from typing import Optional
from modules.wake_word_listener import WakeWordListener
from modules.command_processor import CommandProcessor
import config
from modules.logging_utils import setup_logger, log_info, log_success, log_warning, log_error, log_debug


class Orchestrator:
    """
    Application lifecycle manager.

    Manages wake word detection and delegates command processing.
    """

    def __init__(
        self,
        command_processor: Optional[CommandProcessor] = None,
        wake_word_listener: Optional[WakeWordListener] = None,
        verbose: bool = True,
        debug: bool = False,
        # Backward compatibility parameters
        mpd_controller=None
    ):
        """
        Initialize Orchestrator.

        Args:
            command_processor: CommandProcessor instance (required for new architecture)
            wake_word_listener: Optional WakeWordListener (created if None)
            verbose: Enable verbose output
            debug: Enable debug logging
            mpd_controller: [DEPRECATED] For backward compatibility only

        Note: If command_processor is None and mpd_controller is provided,
              will create a legacy-style orchestrator for backward compatibility.
        """
        self.verbose = verbose
        self.debug = debug
        self.logger = setup_logger(__name__, debug=debug, verbose=verbose)

        # Handle backward compatibility
        if command_processor is None and mpd_controller is not None:
            log_warning(
                self.logger,
                "Using legacy initialization mode. "
                "Please migrate to: create_production_orchestrator()"
            )
            # Create legacy-style setup
            from modules.factory import create_command_processor
            self.command_processor = create_command_processor(
                mpd_controller=mpd_controller,
                debug=debug,
                verbose=verbose
            )
        elif command_processor is None:
            # No command processor and no legacy params - error
            raise ValueError(
                "CommandProcessor required. Use factory: "
                "from modules.factory import create_production_orchestrator; "
                "orchestrator = create_production_orchestrator()"
            )
        else:
            self.command_processor = command_processor

        # Wake word listener (created lazily in start() if None)
        self.wake_word_listener = wake_word_listener

        # State management
        self.is_processing = False
        self.running = True

        log_info(self.logger, "Orchestrator initialized (new architecture)")

    def start(self):
        """
        Start the orchestrator.

        Initializes wake word listener and begins listening loop.
        """
        log_info(self.logger, "Starting Pi-Sat orchestrator...")

        # Setup signal handlers
        try:
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
        except Exception:
            pass

        # Create wake word listener if not provided
        if self.wake_word_listener is None:
            self.wake_word_listener = WakeWordListener(debug=self.debug)

        # Connect wake word detection to our handler
        self.wake_word_listener._notify_orchestrator = self._on_wake_word_detected

        # Start listening
        try:
            self.wake_word_listener.start_listening()
        except KeyboardInterrupt:
            log_info(self.logger, "Keyboard interrupt received")
            self.stop()
        except Exception as e:
            log_error(self.logger, f"Orchestrator error: {e}")
            self.stop()

    def _on_wake_word_detected(self, stream=None, input_rate=None):
        """
        Handle wake word detection.

        Args:
            stream: Active audio stream from wake word listener (for immediate recording)
            input_rate: Stream sample rate

        Plays wake sound and delegates command processing.
        Stream reuse eliminates ~200ms latency from creating new PyAudio stream.
        """
        if self.is_processing:
            log_warning(self.logger, "Ignoring wake word - already processing command")
            return

        log_success(self.logger, "🔔 WAKE WORD DETECTED!")
        # Wake sound is played by WakeWordListener (non-blocking)
        # Recording starts IMMEDIATELY while wake sound plays
        # Skip time is configurable (0.0 = instant, 0.7 = skip full wake sound)
        self.is_processing = True

        try:
            # Delegate to command processor with stream context
            # skip_initial_seconds from config allows instant recording (0.0) or clean recording (0.7)
            self.command_processor.process_command(
                stream=stream,
                input_rate=input_rate,
                skip_initial_seconds=config.WAKE_SOUND_SKIP_SECONDS
            )
        finally:
            self.is_processing = False
            log_info(self.logger, "✅ Ready for next wake word")

    def _signal_handler(self, signum, frame):
        """Handle termination signals"""
        log_info(self.logger, "Shutting down orchestrator...")
        self.running = False
        self.stop()
        try:
            sys.exit(0)
        except SystemExit:
            pass

    def stop(self):
        """
        Stop the orchestrator and cleanup resources.
        """
        self.running = False

        # Stop wake word listener
        if hasattr(self, 'wake_word_listener') and self.wake_word_listener:
            try:
                self.wake_word_listener.stop_listening()
            except Exception as e:
                log_error(self.logger, f"Error stopping wake word listener: {e}")

        # Cleanup command processor resources
        if hasattr(self, 'command_processor') and self.command_processor:
            try:
                # Cleanup STT if available
                if hasattr(self.command_processor, 'stt') and self.command_processor.stt:
                    self.command_processor.stt.cleanup()
            except Exception as e:
                log_error(self.logger, f"Error cleaning up command processor: {e}")

        log_info(self.logger, "Orchestrator stopped")

        # Ensure process exits on Ctrl+C when run via shell wrapper
        if __name__ == "__main__":
            try:
                sys.exit(0)
            except SystemExit:
                pass


if __name__ == "__main__":
    # Production entry point using factory
    from modules.factory import create_production_orchestrator

    debug_mode = "--debug" in sys.argv

    print("=" * 60)
    print("Pi-Sat - Offline Voice-Controlled Music Player")
    print("=" * 60)
    print()

    try:
        orchestrator = create_production_orchestrator(debug=debug_mode)
        orchestrator.start()
    except KeyboardInterrupt:
        log_info(orchestrator.logger, "Keyboard interrupt received (main)")
        orchestrator.stop()
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
