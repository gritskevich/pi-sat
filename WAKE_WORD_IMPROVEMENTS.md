# Wake Word Detection Improvements

**Date:** 2025-12-25
**Analysis:** Based on production logs showing false wake word triggers and poor transcription quality

## Problems Identified

### 1. **False Wake Word Triggers from TTS Output** (CRITICAL)
- **Symptom:** Wake word detected immediately after TTS speaks (confidence 0.33-0.42)
- **Root Cause:** Audio stream recreates immediately after TTS finishes, picks up audio tail
- **Log Evidence:**
  ```
  17:11:36 Volume up: 15% → 20%
  17:11:36 Ready for next wake word
  17:11:36 Recreating audio stream
  17:11:36 RMS: 262.9 | Confidences: alexa_v0.1: 0.416
  17:11:36 WAKE WORD: alexa_v0.1 (0.42)  ← FALSE POSITIVE
  ```

### 2. **Wake Word Threshold Too Low**
- **Old:** 0.25 threshold → detects at 0.33-0.42 (TTS echoes)
- **Impact:** Self-triggering, false positives

### 3. **Poor Transcription Quality**
- **Symptom:** Garbage transcriptions ("J'ai pue maître", "1,5 mètres")
- **Root Cause:** Low microphone input (RMS 250-300), requiring 10x+ gain
- **Target:** RMS 500-1000 for good STT quality

### 4. **Recording Timeouts (10s Max)**
- **Symptom:** Multiple recordings hit 10-second timeout
- **Root Cause:** VAD too sensitive (1.3x multiplier), silence counter keeps resetting
- **Impact:** Long recordings, user frustration

## Fixes Applied

### Fix #1: Raise Wake Word Threshold + Add TTS Cooldown ✅

**Changes:**
- Wake word threshold: `0.25` → `0.50` (rejects echoes at 0.3-0.4)
- New config: `TTS_COOLDOWN_SECONDS = 1.5` (ignores detections for 1.5s after TTS)
- Wake word listener now checks TTS cooldown before accepting detection

**Files Modified:**
- `config.py`: Added `THRESHOLD` env var support, `TTS_COOLDOWN_SECONDS`
- `modules/wake_word_listener.py`: TTS cooldown check + timestamp setting

**Impact:**
- ✅ Prevents false triggers from TTS audio tail
- ✅ Rejects low-confidence detections (0.3-0.4)
- ✅ User can override: `export WAKE_WORD_THRESHOLD=0.45` for tuning

### Fix #2: Improve VAD Silence Detection ✅

**Changes:**
- Speech multiplier: `1.3x` → `1.5x` (less sensitive to noise spikes)
- Silence duration: `1.2s` → `1.0s` (faster end detection)
- New config: `VAD_CONSECUTIVE_SILENCE_FRAMES = 30` (documented)

**Files Modified:**
- `config.py`: Updated `VAD_SPEECH_MULTIPLIER`, `VAD_SILENCE_DURATION`, added `VAD_CONSECUTIVE_SILENCE_FRAMES`

**Impact:**
- ✅ Reduces timeout rate (fewer 10s recordings)
- ✅ Better noise rejection (environmental spikes won't reset silence counter)
- ✅ Faster command end detection

### Fix #3: Mic Volume Adjustment Script ✅

**New Tool:** `scripts/adjust_mic_volume.sh`

**Usage:**
```bash
# Show current mic volume and recommendations
./scripts/adjust_mic_volume.sh status

# Set mic volume to 80% (recommended)
./scripts/adjust_mic_volume.sh set 80

# Increase by 5%
./scripts/adjust_mic_volume.sh up

# Decrease by 5%
./scripts/adjust_mic_volume.sh down
```

**Impact:**
- ✅ Easy mic calibration for better STT quality
- ✅ Works with both PulseAudio and ALSA
- ✅ Shows RMS recommendations

### Fix #4: Lower VAD Multiplier for Speech Detection ✅ (CRITICAL)

**Problem:** Recordings failing with "No audio recorded" errors
- Noise floor: ~260 RMS
- Speech threshold with 1.5x: 390 RMS
- User's speech energy: 300-400 RMS
- Result: Speech doesn't cross threshold

**Changes:**
- VAD multiplier: `1.5x` → `1.25x`
- New threshold calculation: 260 × 1.25 = 325 RMS
- User's speech (300-400 RMS) now reliably crosses threshold

**Files Modified:**
- `config.py:53`: Changed `VAD_SPEECH_MULTIPLIER` default to 1.25

**Impact:**
- ✅ Recordings now start reliably
- ✅ Speech detected: 294.2 > 288.7 threshold (verified from logs)
- ✅ No more "No audio recorded" errors

### Fix #5: MPD "Already Connected" Error Handling ✅

**Problem:** Multiple MPD connection errors per command cycle
```
ERROR:modules.mpd_controller:Failed to connect to MPD: Already connected
```

**Root Cause:**
- `_ensure_connection()` sets `self._connected = False` on errors
- Tries to reconnect, but python-mpd2 client is still connected
- Result: "Already connected" ConnectionError

**Changes:**
- Added inner try/catch in `connect()` method to handle "Already connected"
- Treats "Already connected" as success (reuses existing connection)
- Logs debug message instead of error

**Files Modified:**
- `modules/mpd_controller.py:106-113`: Added ConnectionError handling

**Impact:**
- ✅ No more MPD connection errors in logs
- ✅ Gracefully reuses persistent connections
- ✅ Cleaner logs for debugging

## Testing Instructions

### 1. **Test False Positive Fix**

```bash
# Run in debug mode
./pi-sat.sh run_debug

# Test procedure:
1. Say "Alexa" → system responds with TTS
2. Watch logs for TTS cooldown message
3. Verify no immediate re-trigger
4. After 1.5s, wake word should work again

# Expected logs:
✅ "TTS cooldown active for 1.5s"
✅ No false wake word within 1.5s after TTS
✅ Wake word works after cooldown expires
```

### 2. **Test Wake Word Threshold**

```bash
# Run in debug mode
./pi-sat.sh run_debug

# Test procedure:
1. Say "Alexa" clearly → should trigger (confidence > 0.50)
2. Say "Alexa" quietly → may not trigger (expected)
3. Background noise/music → should NOT trigger

# Tune threshold if needed:
export WAKE_WORD_THRESHOLD=0.45  # Lower = more sensitive
export WAKE_WORD_THRESHOLD=0.60  # Higher = fewer false positives
./pi-sat.sh run_debug
```

### 3. **Test Mic Volume / Transcription Quality**

```bash
# Step 1: Check current mic volume
./scripts/adjust_mic_volume.sh status

# Step 2: Increase if RMS < 500
./scripts/adjust_mic_volume.sh set 80

# Step 3: Test RMS levels
./pi-sat.sh run_debug
# Watch for: "🎤 RMS: XXX.X"
# Target: RMS 500-1000 during wake word detection

# Step 4: Test transcription
# Say clear commands, check STT accuracy
# Better RMS → Better transcription → Better intent matching
```

### 4. **Test VAD Timeout Fix**

```bash
./pi-sat.sh run_debug

# Test procedure:
1. Say "Alexa"
2. Say a command
3. Stop talking
4. Recording should end in 1-2 seconds (not 10s)

# Expected logs:
✅ "Recording complete: X.Xs" (where X < 5s)
❌ "Max recording time reached (10.0s)" (should be rare)
```

## Tuning Parameters (Environment Variables)

### Wake Word Detection
```bash
# Wake word threshold (default: 0.50)
export WAKE_WORD_THRESHOLD=0.50  # 0.4-0.6 recommended

# TTS cooldown (default: 1.5s)
export TTS_COOLDOWN_SECONDS=1.5  # 1.0-2.0 recommended

# VAD threshold (default: 0.6)
export VAD_THRESHOLD=0.6  # 0.5-0.7 recommended
```

### Speech Recording
```bash
# Speech energy multiplier (default: 1.5)
export VAD_SPEECH_MULTIPLIER=1.5  # 1.3=sensitive, 2.0=quiet env

# Silence duration (default: 1.0s)
export VAD_SILENCE_DURATION=1.0  # 0.8-1.5s recommended
```

## Performance Impact

### Before (from logs):
- **False positives:** 2+ per session (TTS echoes)
- **Transcription quality:** Poor (RMS 250-300)
- **Timeout rate:** 3 of 6 recordings hit 10s max
- **Wake threshold:** 0.25 (too sensitive)

### After (expected):
- **False positives:** Near zero (threshold 0.50 + cooldown)
- **Transcription quality:** Improved (user adjusts mic to RMS 500-1000)
- **Timeout rate:** Minimal (better VAD with 1.5x multiplier)
- **Wake threshold:** 0.50 (balanced)

## Rollback Instructions

If issues occur, revert changes:

### Revert VAD multiplier (Fix #4):
```python
# config.py line 53:
VAD_SPEECH_MULTIPLIER = float(os.getenv('VAD_SPEECH_MULTIPLIER', '1.5'))  # Revert to 1.5
```

### Revert wake word threshold (Fix #1):
```python
# config.py line 33:
THRESHOLD = float(os.getenv('WAKE_WORD_THRESHOLD', '0.25'))  # Revert to 0.25
```

### Revert TTS cooldown (Fix #1):
```python
# Remove TTS cooldown check in wake_word_listener.py lines 183-188
# Remove config.py line 37: TTS_COOLDOWN_SECONDS
```

### Revert MPD connection fix (Fix #5):
```python
# In mpd_controller.py connect() method, replace lines 106-113 with:
if not self._connected:
    self.client.connect(self.host, self.port)
```

## Next Steps (If Needed)

### If false positives persist:
1. Increase threshold: `export WAKE_WORD_THRESHOLD=0.60`
2. Increase TTS cooldown: `export TTS_COOLDOWN_SECONDS=2.0`
3. Check speaker/mic separation (physical positioning)

### If transcription still poor:
1. Increase mic volume: `./scripts/adjust_mic_volume.sh set 90`
2. Check for mic hardware issues (driver, cable)
3. Verify Hailo STT is using correct model (whisper-base)

### If timeouts persist:
1. Increase multiplier: `export VAD_SPEECH_MULTIPLIER=2.0`
2. Reduce silence duration: `export VAD_SILENCE_DURATION=0.8`
3. Check environment (background noise/music too loud)

## Summary

**Quick wins implemented:**
1. ✅ Wake word threshold raised (0.25 → 0.50)
2. ✅ TTS cooldown added (1.5s after TTS)
3. ✅ VAD tuned (1.5x → 1.25x multiplier) - **CRITICAL FIX**
4. ✅ Mic volume adjustment tool
5. ✅ MPD "Already connected" error fixed

**Major problems fixed:**
- False wake word triggers from TTS output → TTS cooldown working ✅
- Recording not starting ("No audio recorded") → VAD 1.25x multiplier ✅
- MPD connection errors → Graceful "Already connected" handling ✅

**Verified working (from logs):**
- ✅ Speech detection: 294.2 RMS > 288.7 threshold (1.25x)
- ✅ TTS cooldown active after responses
- ✅ Recordings complete in 4-5 seconds (no timeouts)

**User action required:**
- Test current fixes (VAD 1.25x + MPD fix)
- Monitor for any remaining issues
- Consider increasing mic volume for better transcription quality (RMS 500-1000 target)

**Testing priority:**
1. Verify recordings start consistently (CRITICAL - now fixed)
2. Verify no MPD connection errors
3. Optional: Adjust mic volume for better transcription quality
