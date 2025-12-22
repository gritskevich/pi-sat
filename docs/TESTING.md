# Testing

Single source of truth: `tests/README.md`.

## Quick Commands

```bash
pytest tests/ -q
pytest tests/test_intent_engine.py -q

export PISAT_RUN_HAILO_TESTS=1
pytest tests/test_language_detection.py -q -s
```

## Audio Fixtures

- Registry: `tests/audio_samples/test_metadata.json`
- Suites: `tests/audio_samples/`
