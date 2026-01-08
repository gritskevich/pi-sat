# Pi-Sat Voice Pipeline

Complete flow from wake word to music playback.

---

## Pipeline Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           CONTINUOUS LOOP                                │
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────────┐
│  1. WAKE WORD    │  openwakeword (Alexa detection)
│  Detection       │  ↓ Threshold: 0.01 (very sensitive)
└────────┬─────────┘  ↓ VAD filter: 0.6
         │            ↓ Speex noise suppression: ON
         ↓
    ┌────────────────────────────────────────┐
    │ Wake word detected? ("Alexa")          │
    │ Confidence > 0.01                      │
    │ Cooldown: 0.5s since last detection    │
    └───────┬───────────────────┬────────────┘
            │ NO                │ YES
            │                   ↓
            │          ┌────────────────┐
            │          │  Play Beep     │
            │          │  Close stream  │
            │          └────────┬───────┘
            │                   ↓
            └──────────→  ┌─────────────────┐
                         │  2. RECORDING    │  VAD-based speech capture
                         │  Audio Capture   │  ↓ Silence threshold: 1.0s
                         └────────┬─────────┘  ↓ Max duration: 10s
                                  │            ↓ Sample rate: 48kHz → 16kHz
                                  ↓
                         ┌─────────────────┐
                         │  Normalize RMS  │  Target: 3000 RMS
                         │  (if enabled)   │  ↓ Max gain: 4.0x
                         └────────┬────────┘  ↓ Soft limiter
                                  │
                                  ↓
                         ┌─────────────────┐
                         │  3. STT         │  Hailo Whisper (base)
                         │  Transcription  │  ↓ Language: FR (default)
                         └────────┬────────┘  ↓ Retries: 3 (exponential backoff)
                                  │            ↓ Lock timeout: 15s
                                  ↓            ↓ Auto-rebuild after 2 failures
                         ┌─────────────────┐
                         │ Text output     │
                         │ "joue frozen"   │
                         └────────┬────────┘
                                  │
                                  ↓
                         ┌─────────────────┐
                         │  4. INTENT      │  Fuzzy + Phonetic matching
                         │  Classification │  ↓ Text weight: 40%
                         └────────┬────────┘  ↓ Phonetic (FONEM): 60%
                                  │            ↓ Threshold: 50/100
                                  ↓
                    ┌────────────────────────┐
                    │ Fast path (regex)?     │
                    │ - stop: arrête         │
                    │ - volume_up: plus fort │
                    │ - volume_down: baisse  │
                    └──┬─────────────────┬───┘
                       │ YES             │ NO
                       │                 ↓
                       │        ┌─────────────────┐
                       │        │ Fuzzy matching  │
                       │        │ Best trigger    │
                       │        └────────┬────────┘
                       │                 │
                       ↓                 ↓
                    ┌─────────────────────────┐
                    │ Intent + Parameters     │
                    │ play_music: "frozen"    │
                    │ Confidence: 0.85        │
                    └────────┬────────────────┘
                             │
                             ↓
                    ┌─────────────────┐
                    │  5. VALIDATION  │  Pre-execution checks
                    │  Catalog Check  │  ↓ Search music library
                    └────────┬────────┘  ↓ Confidence thresholds
                             │            ↓ <50%: reject
                             ↓            ↓ 50-80%: uncertain
                    ┌─────────────────────────┐  ↓ ≥80%: confirm
                    │ Valid command?           │
                    │ Song found in catalog?   │
                    │ Confidence acceptable?   │
                    └──┬──────────────────┬────┘
                       │ NO               │ YES
                       │                  ↓
                       │         ┌─────────────────┐
                       │         │  TTS Feedback   │
                       │         │  "Je joue..."   │
                       │         └────────┬────────┘
                       │                  │
                       │                  ↓
                       │         ┌─────────────────┐
                       │         │  6. EXECUTION   │  MPD commands
                       │         │  MPD Control    │  ↓ Software vol: 100%
                       │         └────────┬────────┘  ↓ Shuffle: ON
                       │                  │            ↓ Repeat: playlist
                       │                  ↓
                       │         ┌─────────────────┐
                       │         │  Music Playing  │
                       │         └────────┬────────┘
                       │                  │
                       ↓                  ↓
              ┌─────────────────┐  ┌─────────────────┐
              │  TTS Error      │  │  Recreate       │
              │  "Désolé..."    │  │  Audio Stream   │
              └────────┬────────┘  └────────┬────────┘
                       │                    │
                       └────────┬───────────┘
                                ↓
                       ┌─────────────────┐
                       │  Resume Loop    │
                       │  Listen for     │
                       │  next wake word │
                       └─────────────────┘
```

---

## Stage Details

### 1. Wake Word Detection

**Module**: `modules/wake_word_listener.py`

**Process**:
1. Continuous audio stream (320-sample chunks @ 16kHz)
2. Resample from 48kHz → 16kHz (if needed)
3. Feed to openwakeword model (`alexa_v0.1`)
4. VAD filter (threshold: 0.6)
5. Speex noise suppression (optional, default: ON)
6. Periodic model reset (every 60s)

**Detection**:
- Confidence > 0.01 (very sensitive)
- Cooldown: 0.5s between detections
- Stream closed on detection → command recording

**Config**:
```python
WAKE_WORD_MODELS = ['alexa_v0.1']
THRESHOLD = 0.01                    # Wake confidence
VAD_THRESHOLD = 0.6                 # Voice activity
WAKE_WORD_COOLDOWN = 0.5            # Seconds
ENABLE_SPEEX_NOISE_SUPPRESSION = True
```

---

### 2. Audio Recording

**Module**: `modules/speech_recorder.py`

**Process**:
1. Create fresh audio stream (clean state)
2. Record until silence detected (VAD)
3. Silence threshold: 1.0s
4. Max recording: 10.0s (safety)
5. Normalize RMS to 3000 (if enabled)

**Audio Pipeline**:
```
Mic → 48kHz/16-bit → VAD → Silence detect → 16kHz resample → Normalize
```

**Config**:
```python
RATE = 48000                        # Input sample rate
SAMPLE_RATE = 16000                 # Processing rate
VAD_LEVEL = 2                       # Webrtc VAD aggressiveness
SILENCE_THRESHOLD = 1.0             # Seconds
MAX_RECORDING_TIME = 10.0           # Seconds
AUDIO_NORMALIZATION_ENABLED = True
AUDIO_TARGET_RMS = 3000.0
```

---

### 3. Speech-to-Text (STT)

**Module**: `modules/hailo_stt.py`

**Process**:
1. Write audio to temp WAV file
2. Load → VAD trim → mel spectrogram
3. Hailo Whisper inference (base model)
4. Clean transcription
5. Retry on failure (exponential backoff)

**Retry Logic**:
```
Attempt 1 → fail → wait 0.5s
Attempt 2 → fail → wait 1.0s
Attempt 3 → fail → wait 2.0s
Attempt 4 → fail → rebuild pipeline
```

**Performance**:
- Lock timeout: 15s (prevent deadlock)
- Auto-rebuild: after 2 consecutive failures
- Metrics logged: every 50 requests

**Config**:
```python
HAILO_STT_MODEL = "whisper-base"
LANGUAGE = 'fr'
STT_MAX_RETRIES = 3
STT_RETRY_DELAY = 0.5               # Initial delay
STT_RETRY_BACKOFF = 2.0             # Multiplier
STT_LOCK_TIMEOUT = 15.0             # Seconds
STT_REBUILD_THRESHOLD = 2           # Consecutive failures
```

---

### 4. Intent Classification

**Module**: `modules/intent_engine.py`

**Process**:
1. Clean text (remove "Alexa", normalize hyphens)
2. Fast path: regex for stop/volume (instant)
3. Fuzzy matching: trigger phrases
4. Phonetic matching: FONEM algorithm
5. Combine scores: 40% text + 60% phonetic
6. Extract parameters (song name, volume level, etc.)

**Matching Strategy**:
```
Text:     "joue frozen"
Triggers: ["joue", "mets", "lance", ...]
          ↓
Text fuzzy:     85/100
Phonetic fuzzy: 90/100
          ↓
Combined: (85 × 0.4) + (90 × 0.6) = 88/100
          ↓
Intent: play_music, query="frozen", confidence=0.88
```

**Collision Prevention**:
- `play_music`: requires "joue|mets|lance" keywords
- `pause`: excludes "joue|mets|lance" keywords
- Prevents "arrête de jouer" → pause (should be stop)

**Config**:
```python
FUZZY_MATCH_THRESHOLD = 60          # Min score to match
PHONETIC_WEIGHT = 0.6               # 60% phonetic, 40% text
INTENT_MATCHERS = 'text,phonetic'
```

---

### 5. Command Validation

**Module**: `modules/command_validator.py`

**Process**:
1. Check intent type
2. For `play_music`: search catalog
3. Apply confidence thresholds
4. Generate TTS feedback message
5. Return validated parameters

**Confidence Thresholds**:
- `< 50%`: Reject ("Je n'ai pas trouvé...")
- `50-80%`: Uncertain ("Je pense avoir trouvé...")
- `≥ 80%`: Confirm ("Je joue...")

**Catalog Check**:
```
Query: "frozen"
     ↓
MusicLibrary.search_best()
     ↓
Result: "Disney - Frozen.mp3", confidence=0.92
     ↓
Validation: PASS
     ↓
Feedback: "Je joue Frozen"
Params: {matched_file: "Disney - Frozen.mp3"}
```

---

### 6. Command Execution

**Module**: `modules/command_processor.py`

**Process**:
1. Use validated file path (skip redundant search)
2. MPD: add to queue, play
3. Volume: PulseAudio sink control (not MPD)
4. TTS: speak execution result (if any)

**MPD Architecture**:
```
MPD Software Volume: 100% (fixed, never changed)
         ↓
PulseAudio Sink: Runtime control (0-50%)
         ↓
Hardware Output
```

**Shuffle/Repeat**:
- Default: shuffle ON, repeat playlist
- Queue auto-seeded (all songs)
- "Next" works continuously

**Config**:
```python
MPD_HOST = 'localhost'
MPD_PORT = 6600
MUSIC_LIBRARY = '~/Music'
DEFAULT_SHUFFLE_MODE = True
DEFAULT_REPEAT_MODE = 'playlist'
```

---

### 7. Volume Control

**Module**: `modules/volume_manager.py`

**Architecture**:
```
VolumeManager
    ↓
PulseAudio sink (pactl)
    ↓
MPD @ 100% software volume
    ↓
Speaker
```

**Safety**:
- MAX_VOLUME = 50% (kid-safe)
- VOLUME_STEP = 5% increments
- MASTER_VOLUME = 15% (startup)

**Config**:
```python
MASTER_VOLUME = 15
VOLUME_STEP = 5
MAX_VOLUME = 50                     # Hard limit
```

---

### 8. TTS Feedback

**Module**: `modules/piper_tts.py`

**Process**:
1. Text → Piper TTS (ONNX model)
2. Raw PCM @ 22050 Hz
3. Pipe to pw-play (PulseAudio) OR sox + aplay (ALSA)
4. Play at 100% software, sink controls volume

**Pipeline**:
```
Text → Piper → Raw PCM → pw-play/aplay → Speaker
```

**Config**:
```python
PIPER_MODEL_PATH = 'resources/voices/fr_FR-siwis-medium.onnx'
PIPER_BINARY_PATH = '/usr/local/bin/piper'
PIPER_OUTPUT_DEVICE = 'pulse'
```

---

## Phonetic Matching (FONEM)

**Module**: `modules/phonetic.py`

**Why**: Handle STT errors in cross-language scenarios
- French speaker → English song names
- Example: "frozzen" → "Frozen"

**Algorithm**: FONEM (French-specific)
- 75x faster than BeiderMorse (0.1ms vs 5ms)
- 78.6% accuracy on French STT errors

**Caching Strategy**:
```
Patterns (catalog variants): CACHED (~400 entries)
User queries (unbounded):    NOT CACHED (memory leak prevention)
```

**Performance**:
```
Query: "frozzen" (STT error)
    ↓
Phonetic encode: "FRSN" (0.1ms)
    ↓
Catalog: "Frozen" → "FRSN"
    ↓
Match: 100% phonetic score
    ↓
Combined: (60 × 0.4) + (100 × 0.6) = 84/100
```

---

## Error Handling

### STT Failures

**Transient errors** (network, timeout):
- Retry 3x with exponential backoff
- 0.5s → 1.0s → 2.0s

**Persistent failures**:
- Auto-rebuild pipeline after 2 consecutive failures
- Metrics tracking (success rate, avg retries)

### Wake Word Issues

**Stream recreation failure**:
- Retry 3x with backoff
- Set `running=False` on total failure
- Exit detection loop gracefully

**False positives**:
- Cooldown: 0.5s between detections
- VAD filter: 0.6 threshold
- Speex noise suppression

### MPD Errors

**Connection loss**:
- Auto-reconnect on next command
- Persistent connection pattern
- Best-effort pause/resume (never fail)

---

## Performance Metrics

### Latencies

| Stage | Expected | Notes |
|-------|----------|-------|
| Wake detect | < 500ms | From speech to beep |
| Recording | 1-3s | VAD-based (variable) |
| STT | 1-2s | Hailo inference |
| Intent | < 100ms | Fuzzy + phonetic |
| Validation | < 50ms | Catalog search (cached) |
| MPD play | < 500ms | Queue + start |
| **Total** | **3-5s** | Wake to music |

### Resource Usage

| Resource | Idle | Active |
|----------|------|--------|
| Memory | ~500MB | ~1.5GB |
| CPU | ~5% | ~40% (STT) |
| Hailo | 0% | ~80% (inference) |

---

## Configuration Summary

### ✅ Used (Critical)

```python
# Audio
CHUNK = 320                         # Wake word frame size
RATE = 48000                        # Mic input rate
SAMPLE_RATE = 16000                 # Processing rate

# Wake word
THRESHOLD = 0.01                    # Detection sensitivity
VAD_THRESHOLD = 0.6                 # Voice activity
WAKE_WORD_COOLDOWN = 0.5            # Debounce
ENABLE_SPEEX_NOISE_SUPPRESSION = True

# Recording
VAD_LEVEL = 2                       # Webrtc aggressiveness
SILENCE_THRESHOLD = 1.0             # Stop recording
MAX_RECORDING_TIME = 10.0           # Safety timeout

# Normalization
AUDIO_NORMALIZATION_ENABLED = True
AUDIO_TARGET_RMS = 3000.0

# STT
HAILO_STT_MODEL = "whisper-base"
LANGUAGE = 'fr'
STT_MAX_RETRIES = 3
STT_RETRY_DELAY = 0.5
STT_RETRY_BACKOFF = 2.0
STT_LOCK_TIMEOUT = 15.0
STT_REBUILD_THRESHOLD = 2

# Intent & Music
FUZZY_MATCH_THRESHOLD = 60
PHONETIC_WEIGHT = 0.6
INTENT_MATCHERS = 'text,phonetic'

# Volume
MASTER_VOLUME = 15
VOLUME_STEP = 5
MAX_VOLUME = 50

# MPD
MPD_HOST = 'localhost'
MPD_PORT = 6600
MUSIC_LIBRARY = '~/Music'
DEFAULT_SHUFFLE_MODE = True
DEFAULT_REPEAT_MODE = 'playlist'

# TTS
PIPER_MODEL_PATH = 'resources/voices/fr_FR-siwis-medium.onnx'
PIPER_BINARY_PATH = '/usr/local/bin/piper'
```

### ⚠️ Unused (Remove?)

```python
ELEVENLABS_API_KEY                  # Not used (Piper only)
HAILO_STT_DEBUG                     # Not used (use module debug=True)
PIPER_MODEL_PATH_FR                 # Duplicate of PIPER_MODEL_PATH
PIPER_MODEL_PATH_EN                 # Not used (single language mode)
WAKE_WORD_MODEL_RESET_*             # Used in wake_word_utils (rarely called)
LOW_CONFIDENCE_THRESHOLD            # Used in debug logging only
```

### 🔧 Special Purpose

```python
DEBUG_DUMMY_AUDIO                   # Testing only
INPUT_DEVICE_NAME                   # Auto-detected (None = default)
WAKE_SOUND_SKIP_SECONDS             # Advanced tuning (testing)
STT_BACKEND = 'cpu'                 # Dev fallback (not Hailo)
CPU_STT_MODEL                       # Dev only
```

---

## Flow State Management

### Stream Lifecycle

```
1. Start: Create wake word stream
2. Detect: Close wake stream
3. Record: Create recording stream
4. Process: Close recording stream
5. Recreate: New wake stream
6. Loop: Back to (1)
```

**Critical**: Stream MUST be recreated after each command
- Prevents audio buffer corruption
- Clean state for next detection
- KISS: create/destroy cycle

### Processing Lock

```
is_processing = False  (ready)
    ↓
Wake word detected
    ↓
is_processing = True   (locked)
    ↓
Process command
    ↓
is_processing = False  (ready)
```

**Purpose**: Prevent concurrent command processing
- Ignore wake word during processing
- Single-threaded execution
- No race conditions

---

## Testing

**Unit tests**: 166 passed
- Intent matching
- Music search
- Command validation
- Volume control

**E2E tests** (hardware required):
- Wake word detection
- Full pipeline (audio → music)
- STT accuracy
- French language support

**Run tests**:
```bash
pytest tests/ -v                    # Unit tests
PISAT_RUN_HAILO_TESTS=1 pytest      # + E2E tests
```

---

## Tuning Guide

### Too Many False Positives

```bash
export WAKE_WORD_THRESHOLD=0.5      # Less sensitive (default: 0.01)
export VAD_THRESHOLD=0.7            # Stricter voice detection
```

### Missed Wake Words

```bash
export WAKE_WORD_THRESHOLD=0.005    # More sensitive
export ENABLE_SPEEX=false           # Disable noise suppression
```

### Music Not Found

```bash
export FUZZY_MATCH_THRESHOLD=50     # Lower threshold (default: 60)
export PHONETIC_WEIGHT=0.7          # More phonetic matching
```

### STT Errors

```bash
export STT_MAX_RETRIES=5            # More retries
export STT_REBUILD_THRESHOLD=3      # Rebuild less often
```

### Volume Too Loud

```bash
export MAX_VOLUME=30                # Lower safety limit
export MASTER_VOLUME=10             # Lower startup volume
```

---

## See Also

- **CLAUDE.md** - Module map, principles
- **AUDIO.md** - Audio architecture details
- **WAKE_WORD_DETECTION.md** - Wake word tuning
- **PHONETIC_ALGORITHM_COMPARISON.md** - FONEM benchmarks
