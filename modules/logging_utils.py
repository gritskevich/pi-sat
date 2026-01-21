import logging

from modules.logging_handlers import build_handlers

def setup_logger(name, debug=False, verbose=True):
    """
    Setup unified logger with ISO 8601 datetime formatting and millisecond precision.

    Best practices (2025):
    - ISO 8601 timestamp format for consistency across systems
    - Millisecond precision for debugging and performance monitoring
    - Module-specific loggers using __name__
    - Structured format: timestamp - level - module - message

    Args:
        name: Logger name (typically __name__)
        debug: Enable debug level logging
        verbose: Enable console output

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    level = logging.DEBUG if debug else logging.INFO
    logger.setLevel(level)
    # Prevent double logging via root logger
    logger.propagate = False

    handlers = build_handlers(verbose=verbose, debug=debug)
    if handlers:
        formatter = logging.Formatter(
            fmt='%(asctime)s [%(levelname)-8s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        for handler in handlers:
            handler.setFormatter(formatter)
            logger.addHandler(handler)

    return logger

def log_info(logger, message):
    """Consistent info logging"""
    logger.info(f"ℹ️  {message}")

def log_success(logger, message):
    """Consistent success logging"""
    logger.info(f"✅ {message}")

def log_warning(logger, message):
    """Consistent warning logging"""
    logger.warning(f"⚠️  {message}")

def log_error(logger, message):
    """Consistent error logging"""
    logger.error(f"❌ {message}")

def log_debug(logger, message):
    """Consistent debug logging"""
    logger.debug(f"🔍 {message}")

def log_test(logger, message):
    """Consistent test logging"""
    logger.info(f"🧪 {message}")

def log_audio(logger, message):
    """Consistent audio logging"""
    logger.info(f"🎵 {message}")

def log_stt(logger, message):
    """Consistent STT logging"""
    logger.info(f"📝 {message}")

def log_wake(logger, message):
    """Consistent wake word logging"""
    logger.info(f"🔊 {message}") 
