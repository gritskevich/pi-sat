# Audio Normalization

## What It Does

Normalizes command audio volume for **close vs far speech** to improve STT accuracy.

**Important**: This only affects commands AFTER "Alexa" is detected. Wake word detection is unaffected.

## How It Works

```
Far speech (RMS ~700) → Amplify 4x → RMS ~3000 (optimal for STT)
Close speech (RMS ~7000) → Reduce 0.4x → RMS ~3000 (optimal for STT)
```

**Algorithm**: RMS (Root Mean Square) energy normalization
- Measure audio energy
- Apply gain to reach target level (3000 RMS)
- Soft limit peaks to prevent clipping
- Max gain: 10x (prevents noise amplification)

## Configuration

```bash
# Enable/disable (default: enabled)
export AUDIO_NORMALIZATION_ENABLED=true

# Target RMS level (default: 3000 - optimal for Whisper)
export AUDIO_TARGET_RMS=3000.0
```

## Usage

Automatic - no code changes needed:

```python
recorder = SpeechRecorder()
audio = recorder.record_from_stream(stream, input_rate=48000)
# audio is automatically normalized if enabled
```

Manual (advanced):

```python
from modules.audio_normalizer import normalize_audio

normalized = normalize_audio(audio_bytes, target_rms=3000.0, debug=True)
```

## Testing

```bash
# Run tests
pytest tests/test_audio_normalizer.py -v

# Run demo
python -m modules.audio_normalizer
```

## Troubleshooting

**Still too quiet?**
```bash
# Increase target level
export AUDIO_TARGET_RMS=4000.0

# Or check microphone input volume
./fix_mic_volume.sh
```

**Background noise amplified?**
- Increase microphone input volume (reduces gain needed)
- Run: `./fix_mic_volume.sh`

**Disable normalization:**
```bash
export AUDIO_NORMALIZATION_ENABLED=false
```

## Technical Details

- **Files**: `modules/audio_normalizer.py`, `tests/test_audio_normalizer.py`
- **Dependencies**: NumPy only (no additional libraries)
- **Performance**: ~1ms per second of audio
- **Integration**: Automatic in `SpeechRecorder.record_from_stream()`

## Research

- [RMS normalization](https://superkogito.github.io/blog/2020/04/30/rms_normalization.html)
- [Energy calibration for speech](https://www.codesofinterest.com/2017/04/energy-threshold-calibration-in-speech-recognition.html)
