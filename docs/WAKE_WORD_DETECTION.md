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
INFERENCE_FRAMEWORK = 'tflite'              # TFLite (optimized for Linux)
THRESHOLD = 0.25                            # Detection threshold (0-1)
VAD_THRESHOLD = 0.6                         # Voice Activity Detection (Silero VAD)
ENABLE_SPEEX_NOISE_SUPPRESSION = true       # SpeexDSP noise reduction (ENABLED by default)
```

## OpenWakeWord Built-in Features

### 1. **Speex Noise Suppression** ⭐ (ENABLED by default)

**What it does**: Preprocesses audio to reduce constant background noise/music before prediction

**Performance impact**: Minimal (lightweight algorithm)

**Status**: Installed via requirements.txt, enabled by default

**Impact**: Reduces both false-reject and false-accept rates during music playback

**Disable** (if needed):
```bash
export ENABLE_SPEEX=false
```

**Source**: [OpenWakeWord README](https://github.com/dscripka/openWakeWord/blob/main/README.md), [speexdsp-ns on PyPI](https://pypi.org/project/speexdsp-ns/)

### 2. **Silero VAD (Voice Activity Detection)** ⭐ (ENABLED at 0.6)

**What it does**: Only allows predictions when speech is detected by VAD model

**Current setting**: `VAD_THRESHOLD = 0.6` (balanced)

**Tuning**:
- `0.5` = More lenient (detects more as speech)
- `0.6` = Balanced (recommended)
- `0.7+` = Stricter (fewer false positives, may miss quiet speech)

**Source**: [OpenWakeWord Discussion #4](https://github.com/dscripka/openWakeWord/discussions/4)

### 3. **Detection Threshold**

**Current**: `THRESHOLD = 0.25` (sensitive)

**Default**: OpenWakeWord models trained for `0.5` threshold

**Tuning**:
```bash
export THRESHOLD=0.20  # More sensitive (more false positives)
export THRESHOLD=0.30  # Less sensitive (fewer false positives)
export THRESHOLD=0.50  # Default (OpenWakeWord recommended)
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

1. **Verify Speex is enabled** (should be by default):
   ```bash
   ./pi-sat.sh run
   # Look for: "Speex noise suppression: ENABLED"
   ```

2. **Lower detection threshold**:
   ```bash
   export THRESHOLD=0.20
   ```

3. **Adjust VAD threshold**:
   ```bash
   export VAD_THRESHOLD=0.5  # More lenient
   ```

4. **Check microphone volume** (should be ~30%):
   ```bash
   ./fix_mic_volume.sh
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
   export THRESHOLD=0.30  # or 0.35
   ```

2. **Increase VAD threshold**:
   ```bash
   export VAD_THRESHOLD=0.7  # Stricter
   ```

3. **Verify Speex is enabled** (helps reduce false positives):
   ```bash
   ./pi-sat.sh run
   # Should show: "Speex noise suppression: ENABLED"
   ```

### Issue: Detection stops working after a few minutes

**Potential causes**:
- Model state drift (mitigated by periodic reset every 60s)
- Stream buffer issues (mitigated by stream recreation after commands)

**Our mitigations** (already implemented):
- Periodic model state reset (every 60 seconds)
- Stream recreation after each command
- Buffer flushing

**Source**: [Wyoming-OpenWakeWord Issue #2](https://github.com/rhasspy/wyoming-openwakeword/issues/2)

## Advanced Tuning

### For Very Noisy Environments

```bash
# Speex is already enabled by default
# Adjust thresholds for noisier environments
export VAD_THRESHOLD=0.6
export THRESHOLD=0.30

# Verify microphone levels
./fix_mic_volume.sh
```

### For Quiet Environments

```bash
# More sensitive settings
export THRESHOLD=0.20
export VAD_THRESHOLD=0.5
```

### Testing Different Thresholds

Use debug mode to find optimal threshold:

```bash
./pi-sat.sh run_debug

# Say "Alexa" multiple times at different volumes/distances
# Watch the confidence scores
# Set THRESHOLD to ~20% below typical detection scores
```

## Audio Mixer Considerations

**Multiple audio devices**: System uses default input device

**Check current device**:
```bash
pactl list sources short
```

**Set microphone volume**:
```bash
./fix_mic_volume.sh  # Sets both USB mics to 30%
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
- Speex noise suppression (enabled by default)
- Silero VAD filtering (threshold 0.6)
- Model trained on 30,000+ hours of noise/music
- Periodic model state reset (every 60s)
- Stream recreation after commands
- Tunable thresholds

✅ **Debug mode**:
- Real-time RMS monitoring
- Confidence scores every 0.5s
- Helps identify optimal settings

🎯 **Recommendation**:
1. Keep current defaults (Speex enabled, VAD 0.6)
2. Use debug mode to verify detection
3. Adjust `THRESHOLD` based on environment
4. Run `./fix_mic_volume.sh` to ensure optimal mic levels

**Current configuration is optimized for music playback and background noise.**
