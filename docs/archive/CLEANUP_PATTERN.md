# DRY Cleanup Pattern - Hailo Resource Management

**Challenge accepted!** ✅

## Problem

Hailo STT creates background threads that don't exit cleanly, causing:
- Hung processes after Ctrl+C
- Tests timing out
- Duplicate cleanup code everywhere
- `os._exit()` scattered across files

## Solution: Context Manager + Registry Pattern

**File:** `modules/cleanup_context.py`

### Architecture

```
┌─────────────────────────────────────────┐
│  HailoContext (Context Manager)         │
│  - Auto init on __enter__               │
│  - Auto cleanup on __exit__             │
│  - Signal handling (optional)           │
└─────────────────────────────────────────┘
              │
              ├──> CleanupRegistry (Singleton)
              │    - Global cleanup handlers
              │    - Signal handlers (SIGINT/SIGTERM)
              │    - atexit handlers
              │
              ├──> HailoSTT (singleton)
              │    - Speech-to-text
              │
              └──> IntentEngine
                   - Command classification
```

### Key Features

1. **Context Manager** - Pythonic, automatic cleanup
2. **Global Registry** - Failsafe cleanup even if context fails
3. **Signal Handling** - Catches Ctrl+C, cleans up, exits gracefully
4. **atexit Handler** - Cleanup on normal exit too
5. **force_exit()** - Replaces `os._exit()` with cleanup

## Usage Examples

### Simple Usage (Tests)

```python
from modules.cleanup_context import hailo_stt_only

# Auto cleanup STT only
with hailo_stt_only(language='fr') as stt:
    result = stt.transcribe(audio)
# Cleanup happens automatically!
```

### Full Context (STT + Intent)

```python
from modules.cleanup_context import HailoContext

with HailoContext(language='fr', fuzzy_threshold=35) as ctx:
    # Use ctx.stt for transcription
    text = ctx.stt.transcribe(audio)

    # Use ctx.intent for classification
    intent = ctx.intent.classify(text)
# Auto cleanup of both!
```

### With Signal Handling (Long-running processes)

```python
from modules.cleanup_context import HailoContext

# Enable signal handling for Ctrl+C
with HailoContext(language='fr', handle_signals=True) as ctx:
    while True:
        # Long-running process
        audio = record_audio()
        result = ctx.stt.transcribe(audio)
# Ctrl+C cleans up and exits gracefully!
```

### Production Usage (Orchestrator)

```python
from modules.cleanup_context import HailoContext, force_exit

def main():
    try:
        with HailoContext(
            language='fr',
            handle_signals=True,  # Handle Ctrl+C
            enable_intent=True,
            debug=False
        ) as ctx:
            # Run orchestrator
            orchestrator = Orchestrator(hailo_ctx=ctx)
            orchestrator.start()
    except KeyboardInterrupt:
        print("Interrupted by user")
        force_exit(130)
    except Exception as e:
        print(f"Error: {e}")
        force_exit(1)

    force_exit(0)
```

## Benefits vs Before

### Before (Manual cleanup everywhere)

```python
# test_stt_intent.py (OLD)
stt = None
try:
    stt = HailoSTT(language='fr')
    # ... test code ...
finally:
    if stt:
        stt.cleanup()
    os._exit(exit_code)  # Force exit

# Signal handler
def handler(sig, frame):
    if stt:
        stt.cleanup()
    os._exit(130)
signal.signal(signal.SIGINT, handler)
```

**Problems:**
- 50+ lines of boilerplate
- Easy to forget cleanup
- Global variables for signal handlers
- Duplicated in every file

### After (Context manager)

```python
# test_stt_intent.py (NEW)
from modules.cleanup_context import HailoContext, force_exit

with HailoContext(language='fr', handle_signals=True) as ctx:
    # ... test code uses ctx.stt ...
    pass
# Auto cleanup!

force_exit(exit_code)
```

**Benefits:**
- 5 lines instead of 50
- Can't forget cleanup (automatic)
- No global variables needed
- DRY - reusable everywhere

## Implementation Patterns

### Pattern 1: Simple STT-only

```python
with hailo_stt_only(language='fr') as stt:
    result = stt.transcribe(audio)
```

**Use when:** Only need STT, no intent classification

### Pattern 2: Full Context

```python
with HailoContext(language='fr') as ctx:
    text = ctx.stt.transcribe(audio)
    intent = ctx.intent.classify(text)
```

**Use when:** Need both STT + intent (most common)

### Pattern 3: With Signal Handling

```python
with HailoContext(language='fr', handle_signals=True) as ctx:
    # Long-running process
    while True:
        process()
```

**Use when:** Long-running processes that need Ctrl+C handling

### Pattern 4: Manual Control

```python
ctx = HailoContext(language='fr')
ctx.start()
try:
    # Manual control
    ctx.stt.transcribe(audio)
finally:
    ctx.cleanup()
```

**Use when:** Need manual control (rare)

## Migration Guide

### Tests

**Before:**
```python
stt = HailoSTT(language='fr')
try:
    result = stt.transcribe(audio)
finally:
    stt.cleanup()
```

**After:**
```python
with hailo_stt_only(language='fr') as stt:
    result = stt.transcribe(audio)
```

### Scripts

**Before:**
```python
def main():
    stt = None
    try:
        stt = HailoSTT(language='fr')
        # ... code ...
    except KeyboardInterrupt:
        if stt:
            stt.cleanup()
        os._exit(130)
    finally:
        if stt:
            stt.cleanup()
        os._exit(0)
```

**After:**
```python
from modules.cleanup_context import HailoContext, force_exit

def main():
    try:
        with HailoContext(language='fr', handle_signals=True) as ctx:
            # ... code uses ctx.stt ...
            pass
    except KeyboardInterrupt:
        force_exit(130)

    force_exit(0)
```

### Production (Orchestrator)

**Before:**
```python
# Multiple cleanup points, signal handlers, etc.
```

**After:**
```python
with HailoContext(language='fr', handle_signals=True) as ctx:
    orchestrator = Orchestrator(hailo_ctx=ctx)
    orchestrator.start()
```

## Files Updated

✅ **Created:**
- `modules/cleanup_context.py` - Context manager + registry

✅ **Refactored:**
- `scripts/test_stt_intent.py` - Uses HailoContext now

🔄 **TODO:**
- `tests/test_*.py` - Migrate all tests
- `scripts/test_*.py` - Migrate all scripts
- `modules/orchestrator.py` - Use HailoContext in production

## Testing

```bash
# Test cleanup works
python scripts/test_stt_intent.py

# Test Ctrl+C cleanup
python scripts/test_stt_intent.py
# Press Ctrl+C
# Should see: "Cleaning up..." and clean exit

# Verify no hanging processes
ps aux | grep python  # Should be 0
```

## Advanced: CleanupRegistry

For cases where you need global cleanup coordination:

```python
from modules.cleanup_context import CleanupRegistry

# Register custom cleanup
def my_cleanup():
    print("Cleaning up custom resources")

CleanupRegistry.register(my_cleanup)

# Install signal handlers globally
CleanupRegistry.install_signal_handlers()

# All registered cleanups will run on:
# - SIGINT (Ctrl+C)
# - SIGTERM (kill)
# - Normal exit (atexit)
```

## Philosophy

**KISS Principles:**
1. **Context managers are pythonic** - Use Python's built-in patterns
2. **DRY** - Write cleanup logic once, reuse everywhere
3. **Fail-safe** - Multiple layers (context, registry, atexit, signals)
4. **Explicit is better than implicit** - Clear `with` statement shows scope

## Comparison with Alternatives

| Pattern | Pros | Cons |
|---------|------|------|
| **Context Manager** ✅ | Pythonic, auto cleanup, clear scope | Requires `with` statement |
| Decorator | Works for functions | Not good for main(), less clear |
| Base class | Good for OOP | Not for scripts, inheritance overhead |
| atexit only | Global, simple | No signal handling, cleanup on exit only |
| Manual try/finally | Explicit | Verbose, easy to forget, duplicated |

**Winner: Context Manager + Registry** - Best of all worlds!

---

**Last Updated:** 2025-12-20

**Status:** ✅ Implemented and tested

**Challenge accepted and DESTROYED!** 🎯
