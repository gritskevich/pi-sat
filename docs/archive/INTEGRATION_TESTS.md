# Integration Tests - Full Pipeline

## Overview

Comprehensive integration tests for the complete voice assistant pipeline:
**Wake Word → VAD Recording → STT Transcription → Intent Classification → MPD Execution → TTS Response**

**File:** `tests/test_integration_full_pipeline.py`

## Test Coverage

### ✅ 12 Comprehensive Tests

#### Core Voice Commands (7 tests)
1. **`test_play_music_command`** - Play music command pipeline
2. **`test_pause_command`** - Pause command pipeline
3. **`test_volume_up_command`** - Volume up command pipeline
4. **`test_volume_down_command`** - Volume down command pipeline
5. **`test_add_favorite_command`** - Add to favorites command pipeline
6. **`test_sleep_timer_command`** - Sleep timer command pipeline
7. **`test_skip_command`** - Skip/next command pipeline

#### Component Integration (2 tests)
8. **`test_volume_ducking_integration`** - Volume ducking during voice input
9. **`test_tts_response_integration`** - TTS response after intent execution

#### Error Handling (3 tests)
10. **`test_no_intent_match`** - Handling when no intent matches
11. **`test_empty_transcription`** - Handling empty transcription
12. **`test_fuzzy_matching_integration`** - Fuzzy matching handles typos

## Test Architecture

### Real Components
- **Wake Word Listener** - Real openWakeWord model
- **Speech Recorder** - Real WebRTC VAD
- **STT** - Real Hailo STT (when available, falls back to mock)
- **Intent Engine** - Real fuzzy matching engine

### Mocked Dependencies
- **MPD Controller** - Mocked to avoid MPD daemon requirement
- **TTS** - Mocked to avoid Piper binary requirement
- **Volume Manager** - Mocked for testing

### Graceful Degradation
- Works without Hailo device (uses mock transcription)
- Tests validate each pipeline stage independently
- Comprehensive error handling validation

## Test Flow

Each full pipeline test follows this flow:

1. **Load Audio File** - From `tests/audio_samples/synthetic/`
2. **Wake Word Detection** - Simulate wake word detection
3. **Command Extraction** - Extract command audio (skip wake word)
4. **STT Transcription** - Transcribe command audio
5. **Intent Classification** - Classify transcribed text
6. **MPD Execution** - Execute intent via mocked MPD
7. **TTS Response** - Verify TTS response generation
8. **Volume Ducking** - Verify volume ducking/restoration

## Running Tests

```bash
# Run all integration tests
pytest tests/test_integration_full_pipeline.py -v

# Run specific test
pytest tests/test_integration_full_pipeline.py::TestIntegrationFullPipeline::test_play_music_command -v

# Run with coverage
pytest tests/test_integration_full_pipeline.py --cov=modules --cov-report=html
```

## Test Requirements

### Required
- Python 3.11+
- pytest
- numpy, soundfile (for audio processing)
- unittest.mock (for mocking)

### Optional (for full STT testing)
- Hailo device (falls back to mock transcription if unavailable)

### Not Required
- MPD daemon (mocked)
- Piper TTS binary (mocked)
- Real audio hardware (uses audio files)

## Test Data

Tests use synthetic audio samples from:
- `tests/audio_samples/synthetic/music_control/`
- `tests/audio_samples/synthetic/volume_control/`
- `tests/audio_samples/synthetic/favorites/`
- `tests/audio_samples/synthetic/sleep_timer/`

## Design Principles

- **TDD** - Tests written to verify component integration
- **KISS** - Simple, focused test structure
- **Comprehensive** - Covers all core voice commands
- **Robust** - Handles missing dependencies gracefully
- **Real Components** - Uses real wake word, VAD, STT, intent engine where possible

## Integration with Existing Tests

These integration tests complement existing test suites:
- `test_orchestrator_intent_integration.py` - Intent classification tests
- `test_orchestrator_e2e.py` - End-to-end wake word → STT tests
- `test_intent_engine.py` - Intent engine unit tests
- `test_mpd_controller.py` - MPD controller unit tests

## Future Enhancements

- Add tests for resume/previous commands
- Add tests for play_favorites command
- Add tests with real audio hardware (when available)
- Add performance benchmarks
- Add concurrent command handling tests


