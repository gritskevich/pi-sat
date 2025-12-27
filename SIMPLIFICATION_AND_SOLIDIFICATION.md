# Pi-Sat Simplification & Solidification Plan

**Date**: 2025-12-25

## Recent Simplifications ✅

### 1. Audio Normalization Configuration
**Before**: 4 config settings
**After**: 2 config settings
```python
# Removed (now hardcoded with good defaults):
AUDIO_MAX_GAIN = 10.0
AUDIO_LIMITER_THRESHOLD = 28000.0

# Kept (user-configurable):
AUDIO_NORMALIZATION_ENABLED = true
AUDIO_TARGET_RMS = 3000.0
```

### 2. Documentation Cleanup
**Before**: 250+ line verbose documentation
**After**: 91 line focused documentation
- Removed: `AUDIO_NORMALIZATION_IMPLEMENTATION.md` (redundant)
- Simplified: `docs/AUDIO_NORMALIZATION.md` (70% reduction)
- Clarified: Audio normalization is for COMMANDS, not wake word detection

### 3. Dead Code Removal
**Removed**:
- `WakeWordListener._pause_detection()` method (never called)
- Redundant `self.last_detection_time = time.time()` after stream recreation

### 4. Code Quality
- **Total lines**: ~8,466 lines of core code (modules + config)
- **Tests**: 254 passing, 257 skipped (inactive intents)
- **Dependencies**: Minimal (no new deps for audio normalization)

---

## Wake Word Detection vs Command Normalization

**Clarification** (important distinction):

### Wake Word Detection ("Alexa")
- **When**: Continuous listening for wake word
- **Robustness**: Built into OpenWakeWord model
  - Trained on various noise levels
  - Works during music playback
  - Handles far/close speech natively
- **VAD**: Silero VAD (`VAD_THRESHOLD = 0.6`)
- **Noise suppression**: Optional Speex (`ENABLE_SPEEX_NOISE_SUPPRESSION`)
- **Threshold**: `THRESHOLD = 0.25` (adjustable)

### Command Normalization (NEW)
- **When**: After wake word detected, during command recording
- **Purpose**: Normalize volume for STT accuracy
- **Scope**: Commands only (play music, volume up, etc.)
- **Impact**: No effect on wake word detection

**Result**: Wake word already robust. Command normalization improves STT.

---

## Project Solidification Opportunities

### High Priority

#### 1. Error Recovery & Resilience
**Current State**: Good recovery mechanisms in place
- STT retry logic with exponential backoff
- Stream recreation after commands
- MPD reconnection handling

**Improvements**:
- [ ] Add health check endpoint/command (`./pi-sat.sh status`)
- [ ] Log aggregation for debugging (rotate logs, limit size)
- [ ] Graceful degradation (TTS failure → beep, STT failure → retry with feedback)

#### 2. Configuration Validation
**Current State**: Environment variables, defaults in code
**Improvements**:
- [ ] Validate config on startup (ranges, file paths exist)
- [ ] Config validation tool: `./pi-sat.sh check-config`
- [ ] Clear error messages for invalid config

#### 3. Integration Testing
**Current State**: 254 unit tests passing, integration tests require env vars
**Improvements**:
- [ ] Add smoke test suite (runs on every start)
- [ ] Audio pipeline end-to-end test (wake → record → STT → intent)
- [ ] Mock-based integration tests (no hardware required)

#### 4. Monitoring & Observability
**Current State**: Debug logging, no metrics
**Improvements**:
- [ ] Simple metrics (wake word activations/hour, STT accuracy, errors)
- [ ] Status file (`/tmp/pisat-status.json` with uptime, stats)
- [ ] Log levels configuration (`LOG_LEVEL=INFO`)

### Medium Priority

#### 5. Documentation Consolidation
**Current State**: 65 markdown files (many archived)
**Improvements**:
- [ ] Create single `TROUBLESHOOTING.md` (merge scattered docs)
- [ ] Update `README.md` with quick start
- [ ] Archive old docs (move to `docs/archive/`)

#### 6. Dependency Management
**Current State**: requirements.txt, manual installation
**Improvements**:
- [ ] Lock dependencies (requirements-lock.txt)
- [ ] Verify Hailo SDK compatibility on updates
- [ ] Document minimum/maximum versions

#### 7. Performance Profiling
**Current State**: Anecdotal performance data
**Improvements**:
- [ ] Profile STT latency (wake → result)
- [ ] Measure memory usage over time
- [ ] Identify bottlenecks (if any)

### Low Priority

#### 8. Code Quality Automation
**Improvements**:
- [ ] Pre-commit hooks (ruff, black)
- [ ] CI/CD for tests (GitHub Actions)
- [ ] Coverage reporting

#### 9. User Experience
**Improvements**:
- [ ] LED visual feedback for state (listening, processing, error)
- [ ] Button support (physical button to trigger commands)
- [ ] Volume persistence (remember last volume)

---

## Immediate Action Items

### Wake Word Robustness (If Needed)

If you're experiencing wake word detection issues:

1. **Tune threshold**:
   ```bash
   export THRESHOLD=0.20  # More sensitive (more false positives)
   export THRESHOLD=0.30  # Less sensitive (fewer false positives)
   ```

2. **Adjust VAD**:
   ```bash
   export VAD_THRESHOLD=0.5  # More lenient (detects more as speech)
   export VAD_THRESHOLD=0.7  # Stricter (higher quality speech only)
   ```

3. **Enable noise suppression** (if on Linux):
   ```bash
   export ENABLE_SPEEX=true
   ```

4. **Test microphone levels**:
   ```bash
   ./pi-sat.sh calibrate_vad  # Shows noise floor and speech levels
   ./fix_mic_volume.sh         # Sets mic to 30% (optimal)
   ```

### Command Normalization (Already Implemented)

If command recognition is poor:

1. **Check normalization is enabled** (should be by default):
   ```bash
   # In logs, you should see:
   # "Normalizing: RMS X → 3000.0 (gain: Yx)"
   ```

2. **Adjust target level** (if needed):
   ```bash
   export AUDIO_TARGET_RMS=3500.0  # Louder
   export AUDIO_TARGET_RMS=2500.0  # Quieter
   ```

3. **Disable if causing issues**:
   ```bash
   export AUDIO_NORMALIZATION_ENABLED=false
   ```

---

## Solidification Checklist

### Core Stability
- [x] STT error recovery (retries, rebuild)
- [x] Stream recreation after commands
- [x] MPD connection handling
- [x] Audio normalization for variable distance
- [ ] Config validation on startup
- [ ] Health check command
- [ ] Log rotation

### Testing
- [x] Unit tests (254 passing)
- [x] Audio normalizer tests (12 passing)
- [ ] Smoke test suite
- [ ] Audio pipeline integration test
- [ ] Mock-based tests

### Documentation
- [x] Audio normalization docs
- [x] Dead code removal
- [x] Config simplification
- [ ] Troubleshooting consolidation
- [ ] README update

### Monitoring
- [ ] Basic metrics (activations, errors)
- [ ] Status file/endpoint
- [ ] Log level configuration
- [ ] Performance profiling

---

## Recommended Next Steps

1. **Add config validation**:
   ```bash
   ./pi-sat.sh check-config  # Validates all settings
   ```

2. **Add health check**:
   ```bash
   ./pi-sat.sh status  # Shows uptime, last wake word, errors
   ```

3. **Log rotation**:
   ```python
   # Use RotatingFileHandler for logs
   # Max 10MB per file, keep 5 backups
   ```

4. **Smoke test on start**:
   ```bash
   ./pi-sat.sh test-audio  # Quick audio pipeline check
   ```

---

## Summary

**Simplified** ✅:
- Reduced audio normalization config from 4 → 2 settings
- Simplified documentation (250 → 91 lines)
- Removed dead code (_pause_detection, redundant timestamp)
- Clarified wake word vs command normalization scope

**Solid Foundation** ✅:
- 254 passing tests
- Error recovery mechanisms
- Clean architecture (KISS, DRY, SRP)
- ~8,500 lines of maintainable code

**Next Level** 📋:
- Config validation
- Health monitoring
- Smoke tests
- Documentation consolidation

**Project Status**: Production-ready with clear paths for incremental improvements.
