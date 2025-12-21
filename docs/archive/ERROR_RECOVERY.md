# Error Recovery Integration

**Status:** ✅ Complete (2025-12-14)

## Overview

Implemented comprehensive error recovery for the Pi-Sat voice assistant, focusing on STT (Speech-to-Text) transient failures and system-wide error handling. The system now automatically retries on transient errors and provides user feedback for all failures.

## Implementation

### 1. Retry Utilities Module (`modules/retry_utils.py`)

Generic retry mechanism with exponential backoff for handling transient failures.

**Features:**
- Exponential backoff (delay increases: 0.5s → 1.0s → 2.0s)
- Configurable max retries, initial delay, max delay, and backoff factor
- Exception filtering (only retry specified exceptions)
- Optional retry callback for custom logging
- Preserves function metadata (name, docstring)

**Usage:**
```python
from modules.retry_utils import retry_with_backoff, retry_transient_errors

@retry_with_backoff(max_retries=3, initial_delay=0.5, backoff_factor=2.0)
def flaky_function():
    # Function that may fail transiently
    return result

@retry_transient_errors(max_retries=3)
def network_operation():
    # Automatically retries on ConnectionError, TimeoutError, etc.
    return result
```

### 2. STT Retry Logic (`modules/hailo_stt.py`)

Built-in retry logic in `HailoSTT.transcribe()` method.

**Features:**
- Automatic retry on transient errors (RuntimeError, ConnectionError, OSError, IOError)
- Retries on empty results (may indicate transient failure)
- Configurable via `config.py` settings
- Logs retry attempts and success/failure
- Returns empty string after max retries exhausted

**Configuration:**
```python
# config.py
STT_MAX_RETRIES = 3              # Maximum retry attempts
STT_RETRY_DELAY = 0.5            # Initial retry delay in seconds
STT_RETRY_BACKOFF = 2.0          # Exponential backoff factor
```

**Implementation:**
```python
def _transcribe_with_retry(self, audio_data):
    """Transcribe audio with retry logic for transient errors"""
    max_retries = config.STT_MAX_RETRIES
    initial_delay = config.STT_RETRY_DELAY
    backoff_factor = config.STT_RETRY_BACKOFF
    attempt = 0
    
    while attempt <= max_retries:
        try:
            result = self._transcribe_hailo(audio_data)
            if result:
                return result
            # Retry on empty result
            if attempt < max_retries:
                attempt += 1
                delay = min(initial_delay * (backoff_factor ** (attempt - 1)), 2.0)
                time.sleep(delay)
        except (RuntimeError, ConnectionError, OSError, IOError) as e:
            # Retry on transient errors
            if attempt < max_retries:
                attempt += 1
                delay = min(initial_delay * (backoff_factor ** (attempt - 1)), 2.0)
                time.sleep(delay)
            else:
                log_error(logger, f"STT failed after {max_retries + 1} attempts: {e}")
                return ""
    return ""
```

### 3. Orchestrator Error Handling (`modules/orchestrator.py`)

Enhanced error handling in orchestrator with user notification.

**Features:**
- STT failures: Automatic retry with exponential backoff (built into STT)
- Empty transcription: User notified via TTS error message
- Intent classification errors: Logged, returns None gracefully
- Intent execution errors: Returns error response, user notified via TTS
- Volume restoration: Always restored in finally block (even on errors)
- No silent failures: All errors logged and user notified

**Implementation:**
```python
def _process_command(self):
    # Duck music volume
    self.volume_manager.duck_music_volume(duck_to=config.VOLUME_DUCK_LEVEL)
    
    try:
        # Record and transcribe (STT has built-in retry)
        audio_data = self._record_command()
        text = self.stt.transcribe(audio_data)
        
        if text.strip():
            # Process intent
            intent = self._classify_intent(text)
            if intent:
                response = self._execute_intent(intent)
                if response:
                    self.tts.speak(response)
            else:
                # No intent matched
                error_msg = self.tts.get_response_template('unknown')
                self.tts.speak(error_msg)
        else:
            # No text transcribed - notify user
            error_msg = self.tts.get_response_template('error')
            self.tts.speak(error_msg)
    finally:
        # Always restore music volume (even on errors)
        self.volume_manager.restore_music_volume()
```

## Test Coverage

**Total: 19 tests, all passing**

### Retry Utilities Tests (`tests/test_retry_utils.py`) - 7 tests
- ✅ Retry succeeds on second attempt
- ✅ Retry fails after max attempts
- ✅ Exponential backoff working
- ✅ Max delay respected
- ✅ Exception filtering (only retries specified exceptions)
- ✅ Transient errors decorator works
- ✅ Function metadata preserved

### STT Retry Tests (`tests/test_stt_retry.py`) - 5 tests
- ✅ STT retries on transient error
- ✅ STT fails after max retries
- ✅ STT reloads when unavailable
- ✅ STT handles empty audio gracefully
- ✅ STT retries on connection errors

### Orchestrator Error Recovery Tests (`tests/test_orchestrator_error_recovery.py`) - 7 tests
- ✅ Orchestrator uses STT with retry logic
- ✅ Orchestrator handles STT unavailable
- ✅ Orchestrator notifies user on transcription failure
- ✅ Orchestrator handles empty audio
- ✅ Orchestrator restores volume on error
- ✅ Orchestrator handles intent classification error
- ✅ Orchestrator handles intent execution error

## Configuration

All retry parameters are configurable via `config.py` and environment variables:

```python
# config.py
STT_MAX_RETRIES = int(os.getenv('STT_MAX_RETRIES', '3'))
STT_RETRY_DELAY = float(os.getenv('STT_RETRY_DELAY', '0.5'))
STT_RETRY_BACKOFF = float(os.getenv('STT_RETRY_BACKOFF', '2.0'))
```

## Design Principles

- **KISS**: Simple retry logic without over-engineering
- **TDD**: Tests written first, then implementation
- **Configurable**: Retry behavior adjustable via config
- **Logging**: All errors logged for debugging
- **User Experience**: Users notified of failures via TTS

## Files Created/Modified

**Created:**
- `modules/retry_utils.py` - Retry utility module
- `tests/test_retry_utils.py` - Retry utility tests
- `tests/test_stt_retry.py` - STT retry tests
- `tests/test_orchestrator_error_recovery.py` - Orchestrator error recovery tests
- `docs/ERROR_RECOVERY.md` - This documentation

**Modified:**
- `modules/hailo_stt.py` - Added retry logic to transcription
- `modules/orchestrator.py` - Improved error handling and user notification
- `config.py` - Added retry configuration options
- `CLAUDE.md` - Updated with error recovery documentation

## Verification

All tests pass:
```bash
pytest tests/test_retry_utils.py tests/test_stt_retry.py tests/test_orchestrator_error_recovery.py -v
```

**Result:** 19/19 tests passing ✅

## Next Steps

- Consider adding retry logic for other critical operations (MPD connection, TTS generation)
- Monitor retry success rates in production
- Adjust retry parameters based on real-world failure patterns


