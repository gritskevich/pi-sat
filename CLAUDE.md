# Pi-Sat (LLM Quick Reference)

**Offline voice music player for kids** | Raspberry Pi 5 + Hailo-8L

```
Wake ("Alexa") → Record (VAD) → STT (Hailo Whisper) → Intent → MPD → TTS (Piper)
```

## Fast Commands

```bash
./pi-sat.sh install    # Setup venv, deps, models
./pi-sat.sh run        # Start
./pi-sat.sh run_debug  # Start with continuous monitoring (RMS + confidence scores)
pytest tests/ -q       # Test
```

## Code Principles (Enforced)

- **KISS**: Minimal, no frameworks
- **DRY**: Single source of truth
- **No singletons**: Use `modules/factory.py`
- **SRP**: One responsibility per module

## Module Map

| Component | File | Notes |
|-----------|------|-------|
| Lifecycle | `modules/orchestrator.py` | Main loop |
| Wake word | `modules/wake_word.py` | Stream recreated per cycle (critical!) |
| STT | `modules/hailo_stt.py` | Hailo Whisper pipeline |
| STT (CPU) | `modules/cpu_stt.py` | faster-whisper fallback (dev) |
| Intents | `modules/intent_patterns.py` | 5 patterns (4 active + sleep_timer ready) |
| **Phonetic** | **`modules/phonetic.py`** | **FONEM algorithm (French-specific, 75x faster than BeiderMorse)** |
| Music Search | `modules/music_library.py` | Fuzzy + phonetic hybrid matching |
| Volume | `modules/volume_manager.py` | ONLY volume control |
| Playback | `modules/mpd_controller.py` | MPD @ 100% fixed volume |
| TTS | `modules/piper_tts.py` | Voice responses + response library |
| Audio Norm | `modules/audio_normalizer.py` | RMS normalization (far/close speech) |
| **Sleep Timer** | **`modules/sleep_timer.py`** | **30s fade-out timer (implemented, not active)** |
| **Bedtime** | **`modules/time_scheduler.py`** | **Quiet hours enforcement (implemented, disabled)** |
| **Alarm** | **`modules/morning_alarm.py`** | **Gentle wake-up (implemented, disabled)** |
| **Time Limits** | **`modules/activity_tracker.py`** | **Daily usage tracking (implemented, disabled)** |

## Config (`config.py`)

**Volume Architecture** (critical for kid safety):
- MPD software volume: 100% (never changed)
- PulseAudio sink: Runtime control via VolumeManager
- `MAX_VOLUME=50` enforced at sink level

**Active Intents** (4 active - KISS):
- `play_music` `volume_up` `volume_down` `stop`

**Implemented but Inactive** (add to ACTIVE_INTENTS to enable):
- `set_sleep_timer` - Stop playback after X minutes with 30s fade-out

**Add Intent**:
1. Add patterns to `INTENT_PATTERNS_FR` + `INTENT_PATTERNS_EN` in `modules/intent_patterns.py`
2. Add handler in `modules/command_processor.py` (`_execute_intent`)
3. Add validation in `modules/command_validator.py`
4. Add to `ACTIVE_INTENTS` set to activate
5. Add tests in `tests/`

**Activate Sleep Timer**:
```python
# modules/intent_patterns.py
ACTIVE_INTENTS = {
    'play_music', 'stop', 'volume_up', 'volume_down',
    'set_sleep_timer'  # <-- Add this line
}
```

**Enable Bedtime/Time Limits** (requires integration):
```bash
export BEDTIME_ENABLED=true
export BEDTIME_START=21:00
export BEDTIME_END=07:00
export DAILY_TIME_LIMIT_ENABLED=true
export DAILY_TIME_LIMIT_MINUTES=120  # 2 hours/day
```
Note: Requires wiring into `orchestrator.py` or `command_processor.py`

## Common Tasks

**Debug wake word detection**:
```bash
./pi-sat.sh run_debug  # Shows: RMS levels + "Alexa" confidence scores every 0.5s
```

**Tune wake word sensitivity**:
```bash
export THRESHOLD=0.20     # More sensitive (lower = more detections)
export VAD_THRESHOLD=0.5  # Adjust voice activity detection
```

**Enable more intents**:
```python
# modules/intent_patterns.py
ACTIVE_INTENTS = {
    'play_music', 'stop', 'volume_up', 'volume_down',
    'pause', 'resume'  # <-- Add here
}
```

**Phonetic matching** (intent + music search):
- **Algorithm**: FONEM (French-specific)
- **Performance**: 0.1ms encoding, 78.6% accuracy on French STT errors
- **See**: `docs/PHONETIC_ALGORITHM_COMPARISON.md`, `docs/FONEM_REFACTORING.md`
- **Benchmark**: `python scripts/phonetic_benchmark.py`

**Audio issues**: See `docs/AUDIO.md`, `docs/WAKE_WORD_DETECTION.md`

**Tests**: `pytest tests/ -q` (66 pass intent+music, 22 skip hardware)

## Hardware Reality

- Dev = Prod (no split)
- Changes run on real hardware
- Raspberry Pi 5 + Hailo-8L

## Working Style

- ✅ Short answers, checklists
- ✅ KISS > frameworks
- ✅ Fix root cause only
- ✅ Test after changes (`pytest`)
- ❌ No unrelated refactors
- ❌ No overengineering
