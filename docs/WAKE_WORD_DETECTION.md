# Wake Word Detection ("Alexa") - Robustness Guide

## Overview

Wake word detection uses [OpenWakeWord](https://github.com/dscripka/openWakeWord) with built-in features for handling:
- Background music at various volumes
- Ambient noise
- Variable microphone distance
- Multiple audio mixers/devices

## Current Configuration

```python
# config.py
WAKE_WORD_MODELS = ['alexa_v0.1']           # Pre-trained Alexa model
INFERENCE_FRAMEWORK = 'onnx'                # ONNX Runtime only
WAKE_WORD_THRESHOLD = 0.25                  # Detection threshold (0-1)
WAKE_WORD_COOLDOWN = 0.5                    # Seconds between detections
```

## Detection Features

### 1. **PipeWire Noise Suppression (WebRTC)** ⭐ (optional)

Uses PipeWire's `module-echo-cancel` with WebRTC processing to reduce background noise/music at the audio stack level.

**Enable**:
```bash
scripts/enable_noise_suppression.sh
export INPUT_DEVICE_NAME=PiSat-NS
```

**Note**: This can break wake word detection with PyAudio (virtual source not visible).
Use only for STT experiments, not production wake word.

**Verify**:
```bash
pactl list sources short | grep -i PiSat-NS
```

**Source**:
- PipeWire: https://github.com/PipeWire/pipewire
- WebRTC audio processing: https://github.com/paullouisageneau/webrtc-audio-processing

### 2. **Silero VAD (Voice Activity Detection)** ⭐ (fixed)

**What it does**: Only allows predictions when speech is detected by VAD model

**Current setting**: fixed at `0.6` in code (not user-tunable)

**Source**: [OpenWakeWord Discussion #4](https://github.com/dscripka/openWakeWord/discussions/4)

### 3. **Detection Threshold**

**Current**: `WAKE_WORD_THRESHOLD = 0.25` (sensitive)

**Default**: OpenWakeWord models trained for `0.5` threshold

**Tuning**:
```bash
export WAKE_WORD_THRESHOLD=0.20  # More sensitive (more false positives)
export WAKE_WORD_THRESHOLD=0.30  # Less sensitive (fewer false positives)
export WAKE_WORD_THRESHOLD=0.50  # Default (OpenWakeWord recommended)
```

### 4. **Model Training**

The included `alexa_v0.1` model was trained with:
- ~30,000 hours of negative data (speech, noise, music)
- Dinner Party Corpus dataset (~5.5 hours far-field speech + music)
- Designed to work in noisy environments

**Source**: [OpenWakeWord GitHub](https://github.com/dscripka/openWakeWord)

## Debug Mode - Continuous Monitoring

When running with debug mode, you'll see real-time monitoring:

```bash
./pi-sat.sh run_debug
```

**Output** (every 0.5 seconds):
```
🎤 RMS:  287.3 | Confidences: alexa_v0.1: 0.012
🎤 RMS:  412.8 | Confidences: alexa_v0.1: 0.034
🎤 RMS: 1523.4 | Confidences: alexa_v0.1: 0.789  ← Detection likely!
```

**What to look for**:
- **RMS**: Audio energy level (~200-400 = quiet, ~1000-3000 = speech)
- **Confidences**: Wake word score (>0.25 = detection with current threshold)

## Troubleshooting Detection Issues

### Issue: Not detecting "Alexa" when music is playing

**Solutions**:

1. **Enable PipeWire noise suppression** (optional):
   ```bash
   scripts/enable_noise_suppression.sh
   export INPUT_DEVICE_NAME=PiSat-NS
   ```

2. **Lower detection threshold**:
   ```bash
   export WAKE_WORD_THRESHOLD=0.20
   ```

3. **Check microphone volume** (should be ~30%):
   ```bash
   pactl set-source-volume @DEFAULT_SOURCE@ 80%
   ```

5. **Run debug mode** to see confidence scores:
   ```bash
   ./pi-sat.sh run_debug
   # Say "Alexa" and watch the confidence scores
   ```

### Issue: False activations (triggers without saying "Alexa")

**Solutions**:

1. **Increase detection threshold**:
   ```bash
   export WAKE_WORD_THRESHOLD=0.30  # or 0.35
   ```

2. **Enable PipeWire noise suppression** (optional, helps reduce false positives):
   ```bash
   scripts/enable_noise_suppression.sh
   export INPUT_DEVICE_NAME=PiSat-NS
   ```

### Issue: Detection stops working after a few minutes

**Potential causes**:
- Stream buffer issues (mitigated by stream recreation after commands)

**Our mitigations** (already implemented):
- Stream recreation after each command
- Buffer flushing

**Source**: [Wyoming-OpenWakeWord Issue #2](https://github.com/rhasspy/wyoming-openwakeword/issues/2)

## Advanced Tuning

### For Very Noisy Environments

```bash
# Optional: enable PipeWire noise suppression
scripts/enable_noise_suppression.sh
export INPUT_DEVICE_NAME=PiSat-NS

# Adjust threshold for noisier environments
export WAKE_WORD_THRESHOLD=0.30

# Verify microphone levels
pactl set-source-volume @DEFAULT_SOURCE@ 80%
```

### For Quiet Environments

```bash
# More sensitive settings
export WAKE_WORD_THRESHOLD=0.20
```

### Testing Different Thresholds

Use debug mode to find optimal threshold:

```bash
./pi-sat.sh run_debug

# Say "Alexa" multiple times at different volumes/distances
# Watch the confidence scores
# Set WAKE_WORD_THRESHOLD to ~20% below typical detection scores
```

## Audio Mixer Considerations

**Multiple audio devices**: System uses default input device

**Check current device**:
```bash
pactl list sources short
```

**Set microphone volume**:
```bash
pactl set-source-volume @DEFAULT_SOURCE@ 80%
```

## OpenWakeWord Parameters Not Used (But Available)

### Custom Verifier Models

**What**: Secondary validation models for improved accuracy

**Status**: Not implemented (requires additional model training)

**Potential benefit**: Could reduce false activations for specific speakers/environments

**Source**: [OpenWakeWord Model Parameters](https://github.com/dscripka/openWakeWord/blob/main/openwakeword/model.py)

## Research & References

- [OpenWakeWord GitHub](https://github.com/dscripka/openWakeWord) - Main repository
- [OpenWakeWord README](https://github.com/dscripka/openWakeWord/blob/main/README.md) - Documentation
- [Discussion #4: Background noise and reverberation](https://github.com/dscripka/openWakeWord/discussions/4)
- [Wake Word Detection Guide 2025](https://picovoice.ai/blog/complete-guide-to-wake-word/) - General overview
- [Home Assistant wake word approach](https://www.home-assistant.io/voice_control/about_wake_word/)

## Summary - What Makes Detection Robust

✅ **Already implemented**:
- Optional PipeWire noise suppression (audio stack)
- Silero VAD filtering (threshold 0.6)
- Model trained on 30,000+ hours of noise/music
- Stream recreation after commands
- Tunable thresholds

✅ **Debug mode**:
- Real-time RMS monitoring
- Confidence scores every 0.5s
- Helps identify optimal settings

🎯 **Recommendation**:
1. Keep current defaults (VAD 0.6)
2. Use debug mode to verify detection
3. Adjust `WAKE_WORD_THRESHOLD` based on environment
4. Run `./fix_mic_volume.sh` to ensure optimal mic levels

**Current configuration is optimized for music playback and background noise.**
