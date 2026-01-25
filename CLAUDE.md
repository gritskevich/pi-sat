# Pi-Sat (LLM Quick Reference)

**Offline voice music player for kids** | Raspberry Pi 5 + Hailo-8L

```
Wake ("Alexa" custom) → Record (VAD) → STT (Hailo Whisper) → Intent → MPD → TTS (Piper)
```

## Fast Commands

```bash
./pi-sat.sh install    # Setup venv, deps, models (auto-detects Python 3.11/3.13)
./pi-sat.sh run        # Start
./pi-sat.sh run_debug  # Start with continuous monitoring (RMS + confidence scores)
pytest tests/ -q       # Test
```

## System Requirements

**Debian Trixie (13+) / Raspberry Pi OS**:
- **Python**: 3.13 (system) or 3.11 (via pyenv)
- **Audio**: PipeWire + WirePlumber + pipewire-pulse
- **Hailo SDK**: `python3-hailort` (matches system Python)

**Python 3.13 Support** (Trixie):
- ✅ Hailo SDK native support (system packages)
- ✅ OpenWakeWord via onnxruntime (tflite-runtime not available)
- ✅ Auto-detected and configured by installer
- ✅ Wake word: Auto-switches to ONNX inference framework
- ✅ Audio resampling: 48kHz (mic) → 16kHz (model) via linear interpolation

## Code Principles (Enforced)

- **KISS**: Minimal, no frameworks
- **DRY**: Single source of truth
- **No singletons**: Use `modules/factory.py`
- **SRP**: One responsibility per module

## Module Map

| Component | File | Notes |
|-----------|------|-------|
| Lifecycle | `modules/orchestrator.py` | Main loop |
| Wake word | `modules/wake_word_listener.py` | Dual models (alexa + custom), callback mode |
| STT | `modules/hailo_stt.py` | Hailo Whisper pipeline |
| STT (CPU) | `modules/cpu_stt.py` | faster-whisper fallback (dev) |
| Intents | `modules/intent_engine.py` | Dictionary-driven (intent_dictionary.json) |
| **Phonetic** | **`modules/phonetic.py`** | **FONEM algorithm (French-specific, 75x faster than BeiderMorse)** |
| Music Search | `modules/music_library.py` | Fuzzy + phonetic hybrid matching |
| Volume | `modules/volume_manager.py` | ONLY volume control |
| Playback | `modules/mpd_controller.py` | MPD @ 100% fixed volume |
| **State Machine** | **`modules/playback_state_machine.py`** | **Manages pause/resume during interactions, playback-neutral intents resume** |
| TTS | `modules/piper_tts.py` | Voice responses + response library |
| Audio Norm | `modules/audio_normalizer.py` | RMS normalization (far/close speech) |
| USB Buttons | `modules/usb_button_controller.py` | Physical button event capture |
| **Sleep Timer** | **`modules/sleep_timer.py`** | **30s fade-out timer (implemented, not active)** |

## Config (`config.py`)

**Volume Architecture** (critical for kid safety):
- MPD software volume: 100% (never changed)
- PulseAudio sink: Runtime control via VolumeManager
- `MAX_VOLUME=50` enforced at sink level

**Active Intents** (5 active - KISS):
- `play_music` `pause` `continue` `volume_up` `volume_down`

**Implemented but Inactive** (add to ACTIVE_INTENTS to enable):
- `set_sleep_timer` - Stop playback after X minutes with 30s fade-out

**Add Intent**:
1. Add phrases to `resources/intent_dictionary.json`
2. Add handler in `modules/command_processor.py` (`_execute_intent`)
3. Add validation in `modules/command_validator.py`
4. Add to `ACTIVE_INTENTS` set in `config.py` to activate
5. Add tests in `tests/`

**Activate Sleep Timer**:
```python
# config.py
ACTIVE_INTENTS = {
    'play_music', 'pause', 'continue', 'volume_up', 'volume_down',
    'set_sleep_timer'  # <-- Add this line
}
```

## Common Tasks

**Debug wake word detection**:
```bash
./pi-sat.sh run_debug   # Full system with debug output (RMS + confidence)
./pi-sat.sh test_wake   # 60-second isolated wake word test (diagnostics)
```

**Tune wake word sensitivity**:
```bash
export WAKE_WORD_THRESHOLD=0.20  # More sensitive (lower = more detections)
```

**Enable more intents**:
```python
# config.py
ACTIVE_INTENTS = {
    'play_music', 'pause', 'continue',
    'volume_up', 'volume_down'  # <-- Add here
}
```

**Phonetic matching** (intent + music search):
- **Algorithm**: FONEM (French-specific)
- **Performance**: 0.1ms encoding, 78.6% accuracy on French STT errors
- **See**: `docs/PHONETIC_ALGORITHM_COMPARISON.md`, `docs/FONEM_REFACTORING.md`
- **Benchmark**: `python scripts/phonetic_benchmark.py`

**Hailo**: Module `hailo_pci` must be loaded (`lsmod | grep hailo`, `/dev/hailo0`)
**Audio issues**: See `docs/AUDIO.md`, `docs/WAKE_WORD_DETECTION.md`
**Auto-start**: See `docs/AUTOSTART.md`

**Tests**: `pytest tests/ -q` (66 pass intent+music, 22 skip hardware)

## Hardware Reality

- Dev = Prod (no split)
- Changes run on real hardware
- Raspberry Pi 5 + Hailo-8L + Debian Trixie (13.2)

**USB Audio**:
- **Speaker**: Jieli `4c4a:4155` USB Composite Device (card 0, also has built-in mic)
- **Mic**: Generalplus `1b3f:0004` USB Microphone (card 3, dedicated mic - better quality)
- Audio Stack: **PipeWire + WirePlumber + pipewire-pulse**
- Config: `INPUT_DEVICE_NAME='USB Microphone'` (Generalplus), Output: `default` (Jieli speaker)
- Detect: `aplay -l`, `arecord -l`, `pactl list sources short`

**USB Button Controller**:
- **Device**: Jieli speaker built-in buttons (play/pause, volume up/down) via dynamic `/dev/input/eventX`
- **Module**: `modules/usb_button_controller.py` + `modules/usb_button_router.py`
- **Test**: `python scripts/capture_usb_button_30s.py` to monitor button events
- **Resilience**: ✅ Auto-reconnects on USB disconnect/reconnect with exponential backoff (1s → 30s)
- **Device discovery**: Finds device by name filter, supports dynamic path changes on reconnect

## Working Style

- ✅ Short answers, checklists
- ✅ KISS > frameworks
- ✅ Fix root cause only
- ✅ Test after changes (`pytest`)
- ✅ Use venv for runs (activate `venv` or use `venv/bin/python`)
- ❌ No unrelated refactors
- ❌ No overengineering
