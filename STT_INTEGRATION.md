# Hailo STT Integration

## Overview

The Pi-Sat voice assistant now uses Hailo-accelerated Whisper models for real-time speech recognition. The integration keeps the pipeline initialized for optimal performance.

## Architecture

```
Audio Input → Preprocessing → Hailo Whisper → Postprocessing → Transcription
```

### Components

1. **Audio Preprocessing**
   - VAD (Voice Activity Detection)
   - Audio enhancement and gain adjustment
   - Mel spectrogram generation
   - Chunking for model input

2. **Hailo Whisper Pipeline**
   - Encoder: Processes mel spectrograms
   - Decoder: Generates text tokens
   - Hardware acceleration via Hailo-8L
   - Real-time inference with threading

3. **Postprocessing**
   - Repetition penalty
   - Transcription cleaning
   - Duplicate removal

## Configuration

```python
# config.py
HAILO_STT_MODEL = "whisper-base"  # or "whisper-tiny"
HAILO_STT_HW_ARCH = "hailo8l"     # or "hailo8"
```

## Model Variants

- **Base**: 5-second chunks, higher accuracy
- **Tiny**: 10-second chunks, faster inference

## Hardware Support

- **Hailo-8L**: Optimized for Raspberry Pi 5
- **Hailo-8**: Standard Hailo accelerator

## Usage

```python
from modules.stt import SpeechToText

stt = SpeechToText()  # Initializes pipeline
transcription = stt.transcribe(audio_data)
```

## Code Optimization

The STT module follows KISS/DRY principles:
- **Reuses speech_recognition components** directly
- **Minimal code duplication** - leverages existing preprocessing/postprocessing
- **Simplified initialization** - uses speech_recognition setup
- **Reduced complexity** - single transcribe method with inline processing

## Setup

The setup script automatically downloads required Hailo model files:

```bash
./setup.sh
```

This downloads:
- HEF model files for encoder/decoder
- Tokenization assets
- Model weights and configurations

## Performance

- **Initialization**: ~2-3 seconds (one-time)
- **Inference**: Real-time with hardware acceleration
- **Memory**: ~200MB for base model
- **Latency**: <500ms for typical commands 