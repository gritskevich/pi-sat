# Pi-Sat Tests (French-first)

## Run Tests

```bash
# All tests
pytest tests/ -q

# Specific module
pytest tests/test_music_resolver.py -q
pytest tests/test_intent_engine.py -q

# Hardware tests (Hailo STT)
export PISAT_RUN_HAILO_TESTS=1
pytest tests/test_language_detection.py -v -s
pytest tests/test_e2e_french.py -v -s
pytest tests/test_e2e_french_true.py -v -s
```

## Scope

Active intent tests only. Hardware suites run only with the proper env flags.

## Audio Suites (DRY)

- **Source of truth:** `tests/audio_samples/test_metadata.json`
- **Generate E2E French audio (ElevenLabs):** `python scripts/generate_e2e_french_tests.py`
- **Refresh derived fields (duration, etc.):** `python scripts/refresh_audio_metadata.py`
- **Register a hand-made WAV:** `python scripts/add_audio_test_case.py --suite <id> --group positive|negative ...`

## Diagnostics (Mic timing)

```bash
# Runs 2 representative French patterns by default (ids 1,6)
# Saves timestamped WAVs + timing JSON to /tmp
python scripts/test_e2e_diagnostic.py
```

## Language

- Default STT language is **French** (`LANGUAGE=fr`).
- Tests force French explicitly where it matters (`HailoSTT(language="fr")`).
