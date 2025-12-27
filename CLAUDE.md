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
| Intents | `modules/intent_patterns.py` | 4 active patterns only |
| Volume | `modules/volume_manager.py` | ONLY volume control |
| Playback | `modules/mpd_controller.py` | MPD @ 100% fixed volume |
| TTS | `modules/piper_tts.py` | Voice responses |
| Audio Norm | `modules/audio_normalizer.py` | RMS normalization (far/close speech) |

## Config (`config.py`)

**Volume Architecture** (critical for kid safety):
- MPD software volume: 100% (never changed)
- PulseAudio sink: Runtime control via VolumeManager
- `MAX_VOLUME=50` enforced at sink level

**Active Intents** (4 total - KISS):
- `play_music` `volume_up` `volume_down` `stop`

**Add Intent**:
1. Edit `ACTIVE_INTENTS` in `modules/intent_patterns.py`
2. Add patterns to `INTENT_PATTERNS_FR` + `INTENT_PATTERNS_EN`
3. Add tests in `tests/`

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

**Audio issues**: See `docs/AUDIO.md`, `docs/WAKE_WORD_DETECTION.md`

**Tests**: `pytest tests/ -q` (254 pass, 257 skip inactive intents)

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
