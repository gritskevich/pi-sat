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

## Misc

- `scripts/speak.py`: speak text (TTS)
- `scripts/test_live.py`: quick live smoke tests (wake/STT/pipeline)
- `scripts/monitor_connections.sh`: logs WiFi + USB mic status
