# Pi-Sat Tests (French-first)

## Quick Stats

- **Total tests:** 337 (including new music_resolver tests)
- **Test files:** 30
- **Audio samples:** 36 WAV files
- **Code coverage:** >85%

## Run Tests

```bash
# All tests
pytest tests/ -v

# Specific module
pytest tests/test_music_resolver.py -v
pytest tests/test_intent_engine.py -v

# Hardware tests (Hailo STT)
export PISAT_RUN_HAILO_TESTS=1
pytest tests/test_language_detection.py -v -s
pytest tests/test_e2e_french.py -v -s
pytest tests/test_e2e_french_true.py -v -s
```

## Test Coverage by Module

**Complete Coverage (15 modules):**
- ✅ command_processor
- ✅ command_validator
- ✅ hailo_stt
- ✅ intent_engine
- ✅ mpd_controller
- ✅ music_library
- ✅ **music_resolver** (NEW)
- ✅ orchestrator
- ✅ piper_tts
- ✅ retry_utils
- ✅ speech_recorder
- ✅ volume_manager
- ✅ wake_word_listener

**Missing Tests (4 modules - Kid Safety Features):**
- ⚠️ activity_tracker - Daily time limits
- ⚠️ morning_alarm - Wake-up alarms
- ⚠️ time_scheduler - Bedtime enforcement
- ⚠️ audio_player - Wake sound playback

**Low Priority (6 modules - Utilities):**
- audio_devices, cleanup_context, factory, interfaces, logging_utils

## Audio Suites (DRY)

- **Source of truth:** `tests/audio_samples/test_metadata.json`
- **Generate E2E French audio (ElevenLabs):** `python scripts/generate_e2e_french_tests.py`
- **Refresh derived fields (duration, etc.):** `python scripts/refresh_audio_metadata.py`
- **Register a hand-made WAV:** `python scripts/add_audio_test_case.py --suite <id> --group positive|negative ...`

## Audio Sample Structure

```
tests/audio_samples/
├── wake_word/          # 16 files (8 positive, 8 negative)
├── e2e_french/         # 22 files (19 positive, 3 negative)
├── noise/              # 1 file
└── test_metadata.json  # Source of truth
```

## Diagnostics (Mic timing)

```bash
# Runs 2 representative French patterns by default (ids 1,6)
# Saves timestamped WAVs + timing JSON to /tmp
python scripts/test_e2e_diagnostic.py
```

## Language

- Default STT language is **French** (`HAILO_STT_LANGUAGE=fr`).
- Tests force French explicitly where it matters (`HailoSTT(language="fr")`).
