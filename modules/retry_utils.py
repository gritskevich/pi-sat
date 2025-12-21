"""
Retry utilities for transient error recovery.

Simple retry mechanism with exponential backoff for handling transient failures.
Follows KISS principle - minimal, elegant code.
"""

import time
import logging
from typing import Callable, Optional, Type, Tuple, Any
from functools import wraps

logger = logging.getLogger(__name__)


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 0.5,
    max_delay: float = 2.0,
    backoff_factor: float = 2.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[int, Exception], None]] = None
):
    """
    Decorator for retrying functions with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds (default: 0.5)
        max_delay: Maximum delay in seconds (default: 2.0)
        backoff_factor: Multiplier for delay after each retry (default: 2.0)
        retryable_exceptions: Tuple of exception types to retry on (default: all)
        on_retry: Optional callback called before each retry (attempt_num, exception)
    
    Returns:
        Decorated function that retries on failure
    
    Example:
        @retry_with_backoff(max_retries=3, initial_delay=0.5)
        def transcribe_audio(audio_data):
            return stt.transcribe(audio_data)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        if on_retry:
                            on_retry(attempt + 1, e)
                        else:
                            logger.warning(
                                f"{func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                                f"Retrying in {delay:.2f}s..."
                            )
                        
                        time.sleep(delay)
                        delay = min(delay * backoff_factor, max_delay)
                    else:
                        logger.error(
                            f"{func.__name__} failed after {max_retries + 1} attempts: {e}"
                        )
            
            raise last_exception
        
        return wrapper
    return decorator


def retry_transient_errors(
    max_retries: int = 3,
    initial_delay: float = 0.5,
    max_delay: float = 2.0
):
    """
    Convenience decorator for retrying transient errors.
    
    Retries on common transient exceptions:
    - Connection errors
    - Timeout errors
    - IO errors
    - Runtime errors
    
    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds (default: 0.5)
        max_delay: Maximum delay in seconds (default: 2.0)
    
    Returns:
        Decorated function that retries on transient failures
    """
    transient_exceptions = (
        ConnectionError,
        TimeoutError,
        OSError,
        IOError,
        RuntimeError,
    )
    
    return retry_with_backoff(
        max_retries=max_retries,
        initial_delay=initial_delay,
        max_delay=max_delay,
        retryable_exceptions=transient_exceptions
    )


