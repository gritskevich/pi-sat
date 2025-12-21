# Piper TTS Voice Models

Voice models are not included in the repository due to their size (121MB total).

## Download Instructions

### French Voice (Default)

```bash
wget -O resources/voices/fr_FR-siwis-medium.onnx \
    https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx

wget -O resources/voices/fr_FR-siwis-medium.onnx.json \
    https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx.json
```

### English Voice

```bash
wget -O resources/voices/en_US-lessac-medium.onnx \
    https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx

wget -O resources/voices/en_US-lessac-medium.onnx.json \
    https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
```

## Configuration

Update `PIPER_MODEL_PATH` in `config.py` to point to your preferred voice:

```python
# French (default)
PIPER_MODEL_PATH = "resources/voices/fr_FR-siwis-medium.onnx"

# English
PIPER_MODEL_PATH = "resources/voices/en_US-lessac-medium.onnx"
```

## More Voices

Browse available voices at: https://huggingface.co/rhasspy/piper-voices

Quality levels:
- `low` - Fast, lower quality
- `medium` - Balanced (recommended)
- `high` - Slower, better quality
