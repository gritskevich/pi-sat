# Pi‑Sat (AGENTS / CLAUDE)

AI + developer quick reference. `AGENTS.md` is a symlink to this file.

## Working Style (for AI + humans)

- Short answers. Prefer checklists.
- KISS: minimal, elegant code; avoid “frameworks”.
- Fix root cause; avoid unrelated refactors.
- Prefer targeted tests (`pytest`) after behavior changes.

## Hardware Reality

- Development happens directly on the target hardware: **Raspberry Pi 5 + Hailo‑8L**.
- No dev/prod split: whatever you change runs “for real”.

## What This Project Is

Pi‑Sat is an **offline voice‑controlled music player** for kids:

`Wake word ("Alexa") → record (VAD) → STT (Hailo Whisper) → intent (fuzzy) → MPD playback → Piper TTS`

## Fast Commands

```bash
# Install (creates ./venv, installs deps, downloads wake models)
./pi-sat.sh install

# Run
./pi-sat.sh run
./pi-sat.sh run_debug
./pi-sat.sh run_live

# Tests (recommended)
pytest tests/ -q

# Smoke loops
./pi-sat.sh test_wake_stt
./pi-sat.sh hailo_check
```

## Module Map (where to look)

- Lifecycle: `modules/orchestrator.py`
- Wake word: `modules/wake_word_listener.py`
- Wake beep: `modules/audio_player.py` + `resources/beep-*.wav`
- Pipeline: `modules/command_processor.py`
- Recording/VAD: `modules/speech_recorder.py`
- STT: `modules/hailo_stt.py` (Hailo pipeline under `hailo_examples/speech_recognition/`)
- Intent matching: `modules/intent_engine.py` (`ACTIVE_INTENTS`, `LANGUAGE_PATTERNS`)
- Command validation: `modules/command_validator.py`
- Music query + matching: `modules/music_resolver.py`, `modules/music_library.py`
- Playback: `modules/mpd_controller.py`
- TTS: `modules/piper_tts.py`
- Volume/ducking: `modules/volume_manager.py`

## Config (single source of truth: `config.py`)

Keep docs light; read `config.py` when changing behavior. Key knobs:

- Language: `HAILO_STT_LANGUAGE` (`fr` default; `en` optional)
- Wake word:
  - `THRESHOLD` (sensitivity)
  - `WAKE_WORD_COOLDOWN` (post-command lockout)
  - `VAD_THRESHOLD` (openWakeWord Silero VAD gating)
- Recording:
  - `VAD_LEVEL`, `SILENCE_THRESHOLD`, `MAX_RECORDING_TIME`
  - `VAD_SPEECH_MULTIPLIER`, `VAD_SILENCE_DURATION`, `VAD_MIN_SPEECH_DURATION`
- Audio:
  - `PIPER_OUTPUT_DEVICE`, `OUTPUT_ALSA_DEVICE`
  - `WAKE_SOUND_PATH`, `WAKE_SOUND_SKIP_SECONDS`, `BEEP_VOLUME`, `TTS_VOLUME`
- Volume safety:
  - `VOLUME_DUCK_LEVEL`, `MAX_VOLUME`

## Common Changes

- Enable more intents:
  - Edit `ACTIVE_INTENTS` in `modules/intent_patterns.py` (NOT intent_engine.py)
  - Add triggers + extraction patterns in `INTENT_PATTERNS_FR` / `INTENT_PATTERNS_EN`
  - Add/adjust tests in `tests/`
  - See `docs/INTENT_OPTIMIZATION_2025.md` for comprehensive guide
- Audio/device issues:
  - Use `docs/AUDIO.md` (canonical)
  - MPD device is configured in `~/.mpd/mpd.conf`

## Currently Active Intents (16 total)

Core playback: play_music, play_favorites, pause, resume, stop, next, previous
Volume: volume_up, volume_down, set_volume
Favorites: add_favorite
Advanced: repeat_song, repeat_off, shuffle_on, shuffle_off

More intents defined but not active: sleep_timer, play_next, add_to_queue, set_alarm, etc.
Activate by adding to `ACTIVE_INTENTS` in `modules/intent_patterns.py`

## Doc Map

- `docs/README.md` – minimal doc index
- `docs/AUDIO.md` – audio routing + volume behavior
- `tests/README.md` – tests (and which require hardware)
- `docs/archive/` – historical notes (usually ignore)
