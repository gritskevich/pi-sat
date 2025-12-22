# French E2E Test Suite - Summary

**Date:** 2025-12-21
**Status:** ✅ 10/10 tests passing (100%)

## Overview

Two levels of E2E testing:

**1. Component Integration Tests** (`test_e2e_french.py`)
- Wake Word Detection → STT → Intent Classification
- Manual orchestration of components
- Fast, focused validation

**2. True E2E Tests** (`test_e2e_french_true.py`)
- Complete CommandProcessor pipeline
- Real STT → Intent → MusicResolver → MPD → TTS
- Validates actual execution flow

## Implementation

### Audio Generation (ElevenLabs)

**Segment-based approach** (matches existing integration tests):
- Generate "Alexa" separately (0.91s)
- Add 0.3s silence with sox
- Generate command separately
- Concatenate all segments

**Voice:** Sarah (EXAVITQu4vr4xnSDxMaL) - French female

### Test Structure

**10 music commands** (French songs/artists for consistent STT):
```
1. Je veux écouter maman                  ✅ Pass
2. Je veux écouter Louane                 ✅ Pass
3. Je veux écouter Stromae                ✅ Pass
4. Je veux écouter On écrit sur les murs  ✅ Pass
5. Je veux écouter Alors on danse         ✅ Pass
6. Tu peux jouer maman                    ✅ Pass
7. Tu peux jouer Louane                   ✅ Pass
8. Tu peux jouer Stromae                  ✅ Pass
9. Tu peux mettre On écrit sur les murs   ✅ Pass
10. Tu peux mettre Alors on danse         ✅ Pass
```

**3 negative tests** (no wake word):
- Joue de la musique
- Tu peux mettre Frozen
- Mets Kids United

## Test Results

### Success Rate
- **Wake word detection:** 10/10 (100%)
- **STT + Intent:** 10/10 (100%)
- **Overall:** 10/10 (100%)

### STT Transcription Variations

Examples showing phonetic search handles variations:
```
Expected: "Je veux écouter Louane"
Got:      "Je veux s'écouter le one."    ✅ Matched

Expected: "Tu peux mettre Alors on danse"
Got:      "Tu peux mettre alors on danse."    ✅ Matched

Expected: "Je veux écouter Stromae"
Got:      "Je veux vous écouter, Stromae."    ✅ Matched (phonetic search)
```

### Why It Works

1. **Intent Engine** normalizes text (lowercase, punctuation removal)
2. **Phonetic search** handles misspellings ("abah" → "ABBA")
3. **Fuzzy matching** handles variations ("le one" → "Louane")

## Key Insights

### Segment-Based Generation Critical

**Before** (single sentence):
- "Alexa. Je veux écouter maman."
- STT: "Ecoutez maman." (wrong!)

**After** (segments):
- "Alexa" + 0.3s + "Je veux écouter maman"
- STT: "Je veux écouter maman?" (correct!)

### Calibrated Skip Duration

**Automatic calculation:**
- Wake word duration: 0.91s (measured from generated audio)
- Pause duration: 0.3s (sox-generated)
- **Total skip: 1.21s** (stored in manifest)

Tests use manifest value → no hardcoded offsets.

## Files

**Generator:** `scripts/generate_e2e_french_tests.py`
- ElevenLabs API integration
- Segment-based concatenation
- Automatic skip duration calculation

**Tests:** `tests/test_e2e_french.py`
- Parametrized test (10 music commands)
- Wake word detection
- STT transcription
- Intent classification

**Audio:** `tests/audio_samples/e2e_french/`
- 10 positive tests (with "Alexa")
- 3 negative tests (no wake word)
- manifest.json (metadata + skip duration)

**Documentation:** `scripts/E2E_FRENCH_TESTS_README.md`

## Usage

**Generate audio:**
```bash
python scripts/generate_e2e_french_tests.py
```

**Run component integration tests:**
```bash
pytest tests/test_e2e_french.py -v
```

**Run true E2E tests (requires Hailo):**
```bash
PISAT_RUN_HAILO_TESTS=1 pytest tests/test_e2e_french_true.py -v
```

**Expected output:**
```
# Component tests
tests/test_e2e_french.py::TestFrenchE2EMusic::test_music_command[0-9]
  10 passed

# True E2E tests
tests/test_e2e_french_true.py::TestFrenchE2ETrue::test_full_pipeline[0-9]
  10 passed
```

## Test Comparison

### Component Integration Tests (`test_e2e_french.py`)

**What it tests:**
```python
# Manual orchestration
wake_detected = wake_word_listener.detect_wake_word(audio)
command_audio = audio[skip_duration:]  # Manual skip
transcript = hailo_stt.transcribe(command_audio)
intent = intent_engine.classify(transcript)
# Assert intent only
```

**Pros:**
- Fast (no full pipeline overhead)
- Focused validation
- Easy to debug

**Cons:**
- Doesn't test real execution flow
- No MusicResolver validation
- No MPD/TTS integration

### True E2E Tests (`test_e2e_french_true.py`)

**What it tests:**
```python
# Real CommandProcessor pipeline
processor = CommandProcessor(
    speech_recorder=FakeSpeechRecorder(audio_bytes),
    stt_engine=hailo_stt,  # REAL
    intent_engine=intent_engine,  # REAL
    mpd_controller=FakeMPD(),  # Mocked but tracks commands
    tts_engine=FakeTTS(),  # Mocked but tracks responses
    volume_manager=FakeVolumeManager()
)

success = processor.process_command()  # FULL PIPELINE

# Validates all steps
transcript = processor._transcribe_audio(audio)
intent = processor._classify_intent(transcript)
# Check MPD commands, TTS responses
```

**Pros:**
- Tests real execution flow
- Validates MusicResolver query extraction
- Validates MPD command generation
- Validates TTS response generation
- Catches integration bugs

**Cons:**
- Slower (full pipeline)
- Requires Hailo hardware

## What We Actually Test

### ✅ Tested (True E2E)
1. **VAD Recording** - FakeSpeechRecorder simulates command audio
2. **Hailo STT** - Real transcription
3. **Intent Classification** - Real intent engine
4. **MusicResolver** - Real query extraction + catalog search
5. **MPD Command Generation** - Tracked via FakeMPD
6. **TTS Response** - Tracked via FakeTTS
7. **Volume Management** - Tracked via FakeVolumeManager

### ❌ NOT Tested
1. **Live Wake Word Detection** - Audio pre-validated
2. **Live VAD Silence Detection** - FakeSpeechRecorder returns full audio
3. **Actual MPD Playback** - Mocked
4. **Actual TTS Playback** - Mocked
5. **Real Microphone Input** - Pre-recorded files

## Conclusion

✅ **Component integration tests: 10/10 passing**
✅ **True E2E tests: 10/10 passing**
✅ **Segment-based audio generation works reliably**
✅ **100% success rate with French songs**
✅ **Phonetic search handles STT variations**

**Key learnings:**
1. Use French song names for consistent STT (English triggers language switching)
2. FakeSpeechRecorder pattern enables real CommandProcessor testing
3. Internal methods (`_transcribe_audio`, `_classify_intent`) enable step validation

**Test coverage:**
- ✅ STT → Intent → MusicResolver → MPD pipeline
- ✅ Query extraction and catalog matching
- ✅ Command generation and TTS responses
- ❌ Live wake word + VAD (would require full orchestrator with audio stream)

The test infrastructure is production-ready and provides high confidence in the command processing pipeline.
