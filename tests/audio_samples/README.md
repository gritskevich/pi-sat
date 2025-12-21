# Audio Test Samples

## Strategy

**Git-tracked (committed):**
- `wake_word/` - Hand-crafted wake word samples (essential)
- `noise/` - Noise samples
- `stt/` - STT test samples
- `e2e/` - End-to-end reference samples

**Generated (excluded from git):**
- `_cache_tts/` - TTS generation cache
- `e2e_french/` - ElevenLabs E2E French tests
- `integration/` - Integration test samples
- `language_tests/english/` - English language tests
- `language_tests/french/` - French language tests
- `language_tests/french_full/` - Full French test suite
- `language_tests/french_full_elevenlabs/` - ElevenLabs French suite
- `synthetic/` - Synthetic test samples
- `commands/` - Command test samples

## Regenerating Audio Samples

After cloning the repo, regenerate excluded samples:

```bash
# Generate language test audio (Piper TTS)
python scripts/generate_language_test_audio.py

# Generate E2E French tests (ElevenLabs - requires API key)
python scripts/generate_e2e_french_tests.py

# Generate music test audio
python scripts/generate_music_test_audio.py

# QA check pauses and format
python scripts/qa_stt_audio_suite.py
```

## Why This Strategy?

**Pros:**
- Smaller repo size (~5MB vs 25MB)
- Faster clone/fetch
- No binary file bloat in git history
- Generation scripts are version controlled

**Cons:**
- Need to regenerate after clone
- Requires TTS setup for full test suite
- First test run takes longer

**Trade-off:** Optimized for development velocity over immediate test availability.
