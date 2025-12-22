# Audio Test Standard (Fixtures)

Single source of truth for test audio: `tests/README.md` + `tests/audio_samples/test_metadata.json`.

## Format Rules

- **Prefer WAV** for wake/STT fixtures:
  - 16 kHz, mono, 16‑bit PCM (model-native, deterministic)
- MP3 is for **music playback library** only (MPD), not test fixtures.

## Suite Maintenance

- Generate/refresh suites via scripts documented in `tests/README.md`.
- If you hand-add a WAV, register it in `tests/audio_samples/test_metadata.json` (use helper scripts).
