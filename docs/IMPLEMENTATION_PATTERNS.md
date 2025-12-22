# Implementation Patterns (LLM‑Oriented)

This doc is a **navigation map + invariants**. The single source of truth is the code and tests.

## Read Order (core pipeline)

- Lifecycle: `modules/orchestrator.py`
- Pipeline: `modules/command_processor.py`
- Wake word: `modules/wake_word_listener.py`
- Recording/VAD: `modules/speech_recorder.py`
- STT (Hailo Whisper): `modules/hailo_stt.py`
- Intent classification: `modules/intent_engine.py`
- Music query + match: `modules/music_resolver.py`, `modules/music_library.py`
- Playback: `modules/mpd_controller.py`
- Voice output: `modules/piper_tts.py`
- Wake beep: `modules/audio_player.py`
- Volume + ducking: `modules/volume_manager.py`

## Non‑Negotiables (keep these true)

- **Offline runtime**: `./pi-sat.sh run` must not require network.
- **Audio rates**: device input `config.RATE` (48k) → models expect `config.SAMPLE_RATE` (16k).
- **Wake debounce**: repeated triggers are suppressed by `config.WAKE_WORD_COOLDOWN`.
- **Recording end**: dual detection (WebRTC VAD AND energy threshold) + `VAD_SILENCE_DURATION`.
- **STT language**: forced via `config.HAILO_STT_LANGUAGE` (default `fr`).
- **Production scope**: only `ACTIVE_INTENTS` in `modules/intent_engine.py`.
- **Music UX**: play *best match*; use confidence for messaging (`modules/music_resolver.py`).
- **Playback UX**: continuous shuffle by default (MPD `random=1` + `repeat=1`), and `play <song>` keeps a real queue so the next track is random.
- **Volume isolation**: music uses MPD volume; TTS/beep use per‑stream volume (`docs/AUDIO.md`).

## Change Map (if you change X, also touch Y)

- Wake word sensitivity/cooldown → `config.py`, `tests/test_wake_word_listener.py`
- VAD thresholds → `config.py`, `./pi-sat.sh calibrate_vad`, `tests/test_speech_recorder*.py`
- Intent triggers/extraction → `modules/intent_engine.py`, `tests/test_intent_engine.py`, `tests/test_music_resolver.py`
- Hybrid/phonetic matching → `modules/music_library.py`, `tests/test_music_library.py`, `scripts/test_phonetic_search.py`
- MPD control/queue/volume → `modules/mpd_controller.py`, `tests/test_mpd_controller.py`
- Audio routing/volume isolation → `docs/AUDIO.md`, `tests/test_volume_integration.py`, `scripts/test_volume_independence.py`

## Debug Loops

- Pipeline logs: `./pi-sat.sh run_live`
- Wake diagnostics: `./pi-sat.sh run_debug`
- MPD sanity: `mpc status && mpc outputs`
