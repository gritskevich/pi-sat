import signal
import sys
import threading
from typing import Optional
from modules.wake_word_listener import WakeWordListener
from modules.command_processor import CommandProcessor
import config
from modules.logging_utils import setup_logger, log_info, log_success, log_warning, log_error, log_debug
from modules.control_events import ControlEvent, EVENT_WAKE_WORD_DETECTED


class Orchestrator:
    def __init__(
        self,
        command_processor: Optional[CommandProcessor] = None,
        wake_word_listener: Optional[WakeWordListener] = None,
        verbose: bool = True,
        debug: bool = False,
        event_bus=None
    ):
        self.verbose = verbose
        self.debug = debug
        self.logger = setup_logger(__name__, debug=debug, verbose=verbose)

        if command_processor is None:
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
        self._processing_lock = threading.Lock()
        self.running = True
        self.usb_button_router = None
        self.event_bus = event_bus

        log_info(self.logger, "Orchestrator initialized (new architecture)")

    def start(self):
        log_info(self.logger, "Starting Pi-Sat orchestrator...")

        # Setup signal handlers
        try:
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
        except (ValueError, OSError) as e:
            # Signal handlers can't be set in some environments (e.g., threads, containers)
            log_warning(self.logger, f"Could not register signal handlers: {e}")
            log_warning(self.logger, "Graceful shutdown on SIGINT/SIGTERM may not work")
        except Exception as e:
            log_error(self.logger, f"Unexpected error registering signal handlers: {e}")

        # Create wake word listener if not provided
        if self.wake_word_listener is None:
            self.wake_word_listener = WakeWordListener(debug=self.debug, event_bus=self.event_bus)

        if getattr(config, "STARTUP_CALIBRATION_ENABLED", False):
            try:
                seconds = float(getattr(config, "STARTUP_CALIBRATION_SECONDS", 2.0))
                if hasattr(self.command_processor, "speech_recorder"):
                    self.command_processor.speech_recorder.calibrate_ambient(seconds=seconds)
            except Exception as e:
                log_warning(self.logger, f"Startup calibration skipped: {e}")

        if getattr(config, "USB_BUTTON_ENABLED", False) and self.event_bus:
            try:
                from modules.usb_button_router import create_usb_button_router
                self.usb_button_router = create_usb_button_router(
                    event_bus=self.event_bus,
                    debug=self.debug
                )
            except Exception as e:
                log_warning(self.logger, f"USB button initialization failed: {e}")
        elif getattr(config, "USB_BUTTON_ENABLED", False):
            log_warning(self.logger, "USB button enabled but EventBus is missing")

        if self.event_bus:
            self.event_bus.subscribe(EVENT_WAKE_WORD_DETECTED, self._on_wake_word_detected)
        else:
            # Fallback for direct wake word callback without event bus
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

    def _on_wake_word_detected(self, event: ControlEvent | None = None):
        with self._processing_lock:
            if self.is_processing:
                log_warning(self.logger, "Ignoring wake word - already processing command")
                return
            self.is_processing = True

        log_success(self.logger, "🔔 WAKE WORD DETECTED!")
        # Wake sound already played by WakeWordListener

        def _run_command():
            try:
                # Delegate to command processor (creates its own recording stream)
                self.command_processor.process_command()
            finally:
                with self._processing_lock:
                    self.is_processing = False
                log_info(self.logger, "✅ Ready for next wake word")

        # Avoid blocking the event bus thread
        if self.event_bus and event is not None:
            threading.Thread(target=_run_command, daemon=True).start()
        else:
            _run_command()

    def _signal_handler(self, signum, frame):
        log_info(self.logger, "Shutting down orchestrator...")
        self.running = False
        self.stop()
        try:
            sys.exit(0)
        except SystemExit:
            pass

    def stop(self):
        self.running = False

        # Stop wake word listener
        if hasattr(self, 'wake_word_listener') and self.wake_word_listener:
            try:
                self.wake_word_listener.stop_listening()
            except Exception as e:
                log_error(self.logger, f"Error stopping wake word listener: {e}")

        # Stop USB button controller
        if self.usb_button_router:
            try:
                self.usb_button_router.stop()
            except Exception as e:
                log_error(self.logger, f"Error stopping USB button router: {e}")

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
    orchestrator = None

    print("=" * 60)
    print("Pi-Sat - Offline Voice-Controlled Music Player")
    print("=" * 60)
    print()

    try:
        orchestrator = create_production_orchestrator(debug=debug_mode)
        orchestrator.start()
    except KeyboardInterrupt:
        if orchestrator is not None:
            log_info(orchestrator.logger, "Keyboard interrupt received (main)")
            orchestrator.stop()
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
