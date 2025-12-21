# Pi-Sat Test Suite

## Test Coverage Summary

### ✅ Intent Engine Tests (51/51 passing)
**File:** `test_intent_engine.py`

Comprehensive tests for fuzzy command classification:

- **Basic Commands**
  - Play, pause, resume, stop
  - Next, previous
  - Volume up/down
  - Add to favorites, play favorites

- **Parameter Extraction**
  - Play with song name
  - Sleep timer with duration
  - Variations and edge cases

- **Fuzzy Matching**
  - Typo tolerance
  - Case insensitivity
  - Polite commands with extra words
  - Filler words handling

- **Music Search**
  - Exact match
  - Typo handling
  - Partial match
  - Empty library handling

- **Integration Tests**
  - Play command pipeline
  - Sleep timer pipeline
  - Multiple command sequence

- **French Coverage**
  - French commands (play/pause/resume/stop/next/previous/volume)
  - Accented phrases (arrête, répète, aléatoire, précédent)
  - Kid-friendly phrasing (je veux écouter, fais-moi écouter, etc.)
  - Alexa-prefixed commands (ok alexa, salut alexa)
  - Playlist-based artist and song names
  - Song + artist queries ("chanson de artiste")

**Coverage:** Intent classification, fuzzy matching, parameter extraction, music search

---

### ✅ MPD Controller Tests (33/33 passing)
**File:** `test_mpd_controller.py`

Complete MPD interaction tests with mocked client:

- **Connection Management** (3 tests)
  - Connect/disconnect
  - Singleton pattern
  - Auto-reconnection

- **Playback Control** (7 tests)
  - Play with/without query
  - Pause, resume, stop
  - Next, previous

- **Volume Control** (6 tests)
  - Volume up/down with caps
  - Volume ducking for voice input
  - Restore after ducking

- **Music Search** (3 tests)
  - Fuzzy search
  - Typo handling
  - Empty library

- **Playlist Management** (5 tests)
  - Play favorites
  - Add to favorites
  - Error handling

- **Sleep Timer** (3 tests)
  - Set timer
  - Cancel timer
  - Timer workflow

- **Integration Tests** (3 tests)
  - Play pipeline
  - Volume ducking pipeline
  - Favorites workflow

**Coverage:** All MPD operations, error handling, singleton pattern, threading

---

### ⚠️ Piper TTS Tests (7/14 passing)
**File:** `test_piper_tts.py`

**Passing Tests:**
- Initialization tests (custom model, missing model validation)
- Response templates
- Empty text handling
- Missing binary validation
- Convenience function

**Failing Tests (Expected - Integration Tests):**
- Real speech generation (requires Piper binary)
- Audio file generation (requires sox)
- Subprocess calls (requires actual Piper)

**Note:** Integration tests fail in unit test environment without Piper binary installed. These are expected to pass on the actual Raspberry Pi with Piper installed.

---

## Running Tests

### Run All Tests
```bash
source venv/bin/activate
python -m pytest tests/ -v
```

### Run Specific Module
```bash
# Intent Engine
python -m pytest tests/test_intent_engine.py -v

# MPD Controller
python -m pytest tests/test_mpd_controller.py -v

# Piper TTS
python -m pytest tests/test_piper_tts.py -v
```

### Run with Coverage
```bash
python -m pytest tests/ --cov=modules --cov-report=html
```

### Quick Test (via pi-sat.sh)
```bash
./pi-sat.sh test
```

---

## Test Statistics

| Module | Tests | Passing | Failing | Coverage |
|--------|-------|---------|---------|----------|
| Intent Engine | 51 | 51 | 0 | ~95% |
| MPD Controller | 33 | 33 | 0 | ~90% |
| Piper TTS | 14 | 7 | 7* | ~70% |
| **Total** | **98** | **91** | **7*** | **~85%** |

\* Piper TTS failures are integration tests requiring actual binary

---

## Test Organization

```
tests/
├── test_intent_engine.py       # ✅ 51 tests (fuzzy matching, classification, FR coverage)
├── test_mpd_controller.py      # ✅ 33 tests (MPD operations, mocked)
├── test_piper_tts.py          # ⚠️ 14 tests (7 pass, 7 integration)
├── test_wake_word.py          # ✅ Existing tests
├── test_speech_recorder.py    # ✅ Existing tests
├── test_hailo_stt_suite.py    # ✅ Existing tests
└── README.md                  # This file
```

---

## Next Steps

According to CLAUDE.md, the next components to implement are:

1. **Mic Mute Detector** (`test_mic_mute_detector.py`)
   - Audio level monitoring
   - Unmute detection
   - Callback integration

2. **Orchestrator Integration Tests** (expand existing)
   - End-to-end pipeline with new components
   - Volume ducking during recording
   - TTS response playback

---

**Last Updated:** 2025-12-20
**Test Framework:** pytest 8.4.1
**Python Version:** 3.11.2
