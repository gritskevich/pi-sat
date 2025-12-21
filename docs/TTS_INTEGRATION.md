# TTS Integration Summary

## Overview
Integrated Text-to-Speech (TTS) functionality into the Pi-Sat orchestrator to provide audio feedback to users. The system now uses PiperTTS for all voice responses after intent execution.

## Changes Made

### 1. Fixed Orchestrator TTS Initialization
**File:** `modules/orchestrator.py`

**Issue:** Orchestrator was creating PiperTTS without specifying the audio output device, defaulting to `'default'` instead of using `config.PIPER_OUTPUT_DEVICE`.

**Fix:** Updated orchestrator to explicitly pass `output_device=config.PIPER_OUTPUT_DEVICE` when initializing PiperTTS.

```python
# Before:
self.tts = PiperTTS(volume_manager=self.volume_manager)

# After:
self.tts = PiperTTS(
    volume_manager=self.volume_manager,
    output_device=config.PIPER_OUTPUT_DEVICE
)
```

### 2. Added Audio Device Validation
**File:** `modules/audio_devices.py`

**Added Functions:**
- `list_alsa_devices()` - Lists available ALSA playback devices using `aplay -l`
- `validate_alsa_device(device_name)` - Validates that an ALSA device is available for playback
- `get_default_alsa_device()` - Gets default ALSA device for RPi 5 with fallback logic

**Purpose:** Ensures TTS uses a valid audio device and provides helpful warnings if the configured device is unavailable.

### 3. Enhanced TTS Validation
**File:** `modules/piper_tts.py`

**Added:** Audio device validation in `_validate()` method to check if the configured ALSA device is available before attempting to use it.

**Benefit:** Early detection of audio device issues with helpful error messages.

### 4. Comprehensive Test Suite
**File:** `tests/test_tts_integration.py`

**Tests Created (11 comprehensive tests):**
- `test_tts_initialized_in_orchestrator` - Verifies TTS is initialized
- `test_tts_uses_correct_output_device` - Verifies correct audio device from config
- `test_tts_called_after_intent_execution` - Verifies TTS is called after successful intent
- `test_tts_called_on_no_intent_match` - Verifies TTS called with error message
- `test_tts_called_on_empty_transcription` - Verifies TTS called with error when no text
- `test_tts_called_on_empty_audio_data` - Verifies TTS called when audio data empty
- `test_tts_handles_stt_unavailable` - Verifies TTS called when STT unavailable
- `test_tts_not_called_when_response_is_none` - Verifies TTS not called when response None
- `test_tts_response_for_each_intent_type` - Verifies appropriate responses for all intents
- `test_tts_volume_management` - Verifies volume manager integration
- `test_tts_error_handling` - Verifies graceful error handling
- `test_tts_default_output_device` - Tests default device handling
- `test_tts_custom_output_device` - Tests custom device configuration
- `test_orchestrator_tts_uses_config_device` - Verifies orchestrator uses config device

**Test Coverage:**
- ✅ All success paths (intent execution → TTS response)
- ✅ All error paths (empty transcription, STT unavailable, no intent match)
- ✅ Edge cases (empty audio, None responses, TTS errors)
- ✅ Audio device configuration
- ✅ Volume management integration

### 5. End-to-End Test Script
**File:** `scripts/test_tts.py`

**Purpose:** Comprehensive test script to verify TTS integration works on actual hardware.

**Tests:**
- Audio device validation
- TTS initialization
- TTS with volume manager
- TTS speech playback (actual audio output)
- Orchestrator TTS integration

**Usage:**
```bash
./scripts/test_tts.py
# or
python scripts/test_tts.py
```

## Current TTS Flow

1. **Wake Word Detected** → Orchestrator triggers `_on_wake_word_detected()`
2. **Volume Ducking** → Music volume lowered for better voice input
3. **Voice Recording** → Speech recorded with VAD
4. **STT Transcription** → Audio transcribed to text
5. **Intent Classification** → Text classified into intent
6. **Intent Execution** → MPD command executed
7. **TTS Response** → Response message generated
8. **Audio Output** → TTS speaks response via PiperTTS
9. **Volume Restoration** → Music volume restored

## Configuration

### Audio Device
**Config:** `config.PIPER_OUTPUT_DEVICE` (default: `'default'`)

**Options:**
- `'default'` - System default ALSA device
- `'plughw:0,0'` - Hardware device with automatic format conversion
- `'hw:0,0'` - Direct hardware device (no conversion)

**For RPi 5:**
- `'default'` is recommended for most cases
- `'plughw:0,0'` if you need specific hardware device
- Use `aplay -l` to list available devices

### TTS Volume
**Config:** `config.TTS_VOLUME` (default: `80`)

TTS volume is managed separately from music volume via `VolumeManager`. The volume is temporarily set during TTS playback and restored afterward.

## Testing

### Run Integration Tests
```bash
# Using unittest
python3 -m unittest tests.test_tts_integration -v

# Using pi-sat.sh (requires venv)
./pi-sat.sh test
```

### Run End-to-End Test
```bash
# Test actual audio output
./scripts/test_tts.py
```

### Verify Audio Device
```bash
# List available ALSA devices
aplay -l

# Test device
aplay -D default /path/to/test.wav
```

## Known Issues & Solutions

### Issue: No Audio Output
**Symptoms:** TTS doesn't produce audio

**Solutions:**
1. Check audio device: `aplay -l`
2. Test device: `aplay -D default /path/to/test.wav`
3. Verify volume: `amixer get Master`
4. Check config: `config.PIPER_OUTPUT_DEVICE`

### Issue: Wrong Audio Device
**Symptoms:** Audio plays on wrong device

**Solution:** Update `config.PIPER_OUTPUT_DEVICE` or set `PIPER_OUTPUT_DEVICE` environment variable

### Issue: Volume Too Low/High
**Symptoms:** TTS volume not appropriate

**Solution:** Adjust `config.TTS_VOLUME` (0-100) or use volume manager methods

## Best Practices for RPi 5

1. **Use 'default' device** - Most reliable, handles device switching automatically
2. **Test audio device** - Run `scripts/test_tts.py` after setup
3. **Monitor volume** - Use volume manager for consistent volume levels
4. **Error handling** - TTS errors are logged but don't crash the orchestrator

## Next Steps

- [ ] Test on actual RPi 5 hardware
- [ ] Verify audio output with different devices
- [ ] Test volume management integration
- [ ] Add TTS response customization
- [ ] Consider TTS caching for common responses

## References

- Piper TTS: https://github.com/rhasspy/piper
- ALSA Device Names: https://www.alsa-project.org/wiki/Device_names
- RPi 5 Audio: https://www.raspberrypi.com/documentation/computers/audio.html

