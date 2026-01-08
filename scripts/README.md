# Scripts

Utility scripts for testing and development (French-first).

## Audio Suites

```bash
# Generate ElevenLabs E2E French suite (updates metadata)
export ELEVENLABS_API_KEY="..."
python scripts/generate_e2e_french_tests.py

# Refresh derived fields in metadata (duration, command_duration_s, ...)
python scripts/refresh_audio_metadata.py

# Add/mark a hand-made WAV in metadata
python scripts/add_audio_test_case.py --suite e2e_french --group positive --file <wav> --full-phrase "..." --command "..." --intent play_music --parameters '{"query":"..."}'
```

## Diagnostics (Mic timing + STT)

```bash
# Plays a test WAV, records mic, slices command, runs STT, saves WAVs to /tmp
python scripts/test_e2e_diagnostic.py
```

## Phonetic Algorithm Testing

```bash
# Benchmark all phonetic algorithms (BeiderMorse, FONEM, Soundex, Metaphone, etc.)
python scripts/phonetic_benchmark.py

# Show detailed per-test results
python scripts/phonetic_benchmark.py --debug

# Use custom music directory
python scripts/phonetic_benchmark.py --music-dir /path/to/music
```

See `docs/PHONETIC_ALGORITHM_COMPARISON.md` for research findings.

## Misc

- `scripts/speak.py`: speak text (TTS)
- `scripts/calibrate_vad.py`: tune VAD thresholds
