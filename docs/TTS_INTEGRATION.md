# TTS (Piper) Integration — Notes

Canonical implementation: `modules/piper_tts.py`.

## What Matters

- Output device: `config.PIPER_OUTPUT_DEVICE` (ALSA device passed to `aplay -D`)
- Volume: `config.TTS_VOLUME` is applied per-stream via `sox vol` (does **not** touch global mixer)
- Model + binary:
  - `config.PIPER_MODEL_PATH`
  - `config.PIPER_BINARY_PATH`

## Tests / Debug

- Unit/integration: `pytest tests/test_tts_integration.py -q`
- Quick device sanity:
  ```bash
  aplay -l
  python scripts/speak.py "Test"
  ```

## See Also

- Audio routing + mixers: `docs/AUDIO.md`
