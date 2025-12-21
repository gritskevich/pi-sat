"""
DRY Cleanup Solution for Hailo Resources

Provides context manager + signal handling for guaranteed cleanup.
Works in tests, scripts, and production.

Usage:

    # Simple usage (auto cleanup)
    with HailoContext(language='fr') as ctx:
        result = ctx.stt.transcribe(audio)
        intent = ctx.intent.classify(result)
    # Cleanup happens automatically!

    # With signal handling (for long-running processes)
    with HailoContext(language='fr', handle_signals=True) as ctx:
        while True:
            # Process commands
            pass
    # Catches Ctrl+C and cleans up

    # Manual cleanup (if needed)
    ctx = HailoContext(language='fr')
    ctx.start()
    try:
        ctx.stt.transcribe(audio)
    finally:
        ctx.cleanup()
"""

import os
import sys
import signal
import atexit
from typing import Optional
from contextlib import contextmanager

from .hailo_stt import HailoSTT
from .intent_engine import IntentEngine
from .logging_utils import setup_logger, log_info, log_warning

logger = setup_logger(__name__)


class CleanupRegistry:
    """
    Global registry for cleanup handlers.
    Ensures cleanup even if context manager fails.
    """
    _handlers = []
    _signal_handlers_installed = False

    @classmethod
    def register(cls, cleanup_func):
        """Register a cleanup function"""
        if cleanup_func not in cls._handlers:
            cls._handlers.append(cleanup_func)

    @classmethod
    def unregister(cls, cleanup_func):
        """Unregister a cleanup function"""
        if cleanup_func in cls._handlers:
            cls._handlers.remove(cleanup_func)

    @classmethod
    def cleanup_all(cls):
        """Run all registered cleanup handlers"""
        for handler in cls._handlers:
            try:
                handler()
            except Exception as e:
                log_warning(logger, f"Cleanup handler error: {e}")

    @classmethod
    def install_signal_handlers(cls):
        """Install global signal handlers for cleanup"""
        if cls._signal_handlers_installed:
            return

        def signal_handler(signum, frame):
            log_info(logger, f"Received signal {signum}, cleaning up...")
            cls.cleanup_all()
            os._exit(128 + signum)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Register atexit handler (for normal exit)
        atexit.register(cls.cleanup_all)

        cls._signal_handlers_installed = True


class HailoContext:
    """
    Context manager for Hailo STT with automatic cleanup.

    Handles:
    - Resource initialization
    - Automatic cleanup on exit
    - Signal handling (optional)
    - Registry-based cleanup (failsafe)
    """

    def __init__(
        self,
        language: str = 'fr',
        fuzzy_threshold: int = 35,
        debug: bool = False,
        handle_signals: bool = False,
        enable_intent: bool = True
    ):
        """
        Initialize Hailo context.

        Args:
            language: STT language (default: 'fr')
            fuzzy_threshold: Intent fuzzy match threshold
            debug: Enable debug logging
            handle_signals: Install signal handlers for Ctrl+C/SIGTERM
            enable_intent: Initialize intent engine (set False if not needed)
        """
        self.language = language
        self.fuzzy_threshold = fuzzy_threshold
        self.debug = debug
        self.handle_signals = handle_signals
        self.enable_intent = enable_intent

        self.stt: Optional[HailoSTT] = None
        self.intent: Optional[IntentEngine] = None
        self._cleanup_registered = False

    def start(self):
        """Initialize resources"""
        if self.debug:
            log_info(logger, "Initializing Hailo context...")

        # Initialize STT
        self.stt = HailoSTT(debug=self.debug, language=self.language)

        if not self.stt.is_available():
            raise RuntimeError("Hailo STT initialization failed")

        # Initialize Intent Engine (if enabled)
        if self.enable_intent:
            self.intent = IntentEngine(
                fuzzy_threshold=self.fuzzy_threshold,
                language=self.language,
                debug=self.debug
            )

        # Register cleanup
        CleanupRegistry.register(self.cleanup)
        self._cleanup_registered = True

        # Install signal handlers (if requested)
        if self.handle_signals:
            CleanupRegistry.install_signal_handlers()

        if self.debug:
            log_info(logger, "Hailo context ready")

        return self

    def cleanup(self):
        """Cleanup resources"""
        if self.debug:
            log_info(logger, "Cleaning up Hailo context...")

        # Cleanup STT
        if self.stt is not None:
            try:
                self.stt.cleanup()
            except Exception as e:
                log_warning(logger, f"STT cleanup error: {e}")
            self.stt = None

        # Intent engine has no cleanup (no resources)
        self.intent = None

        # Unregister from global registry
        if self._cleanup_registered:
            CleanupRegistry.unregister(self.cleanup)
            self._cleanup_registered = False

        if self.debug:
            log_info(logger, "Cleanup complete")

    def __enter__(self):
        """Context manager entry"""
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit (auto cleanup)"""
        self.cleanup()
        return False  # Don't suppress exceptions

    def __del__(self):
        """Destructor - last resort cleanup"""
        if self._cleanup_registered:
            self.cleanup()


@contextmanager
def hailo_stt_only(language: str = 'fr', debug: bool = False):
    """
    Simple context manager for STT-only usage (no intent engine).

    Usage:
        with hailo_stt_only(language='fr') as stt:
            result = stt.transcribe(audio)
    """
    stt = None
    try:
        stt = HailoSTT(debug=debug, language=language)
        if not stt.is_available():
            raise RuntimeError("Hailo STT not available")
        yield stt
    finally:
        if stt is not None:
            try:
                stt.cleanup()
            except Exception as e:
                log_warning(logger, f"STT cleanup error: {e}")


def force_exit(exit_code: int = 0):
    """
    Force exit with cleanup.
    Use this instead of sys.exit() or os._exit() to ensure cleanup.
    """
    CleanupRegistry.cleanup_all()
    os._exit(exit_code)
