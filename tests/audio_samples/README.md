# Audio Test Samples

## Strategy

**Git-tracked (committed):**
- `wake_word/` - Hand-crafted "Alexa" samples (essential)
- `noise/` - Noise samples
- `test_metadata.json` - ✅ Source of truth (FR-first) for audio-driven tests

## Regenerating Audio Samples

After cloning the repo, regenerate excluded samples:

```bash
# Generate E2E French tests (ElevenLabs - requires API key)
python scripts/generate_e2e_french_tests.py

# QA check pauses and format (optional)
python scripts/qa_stt_audio_suite.py
```

**Generated (gitignored):**
- `e2e_french/` - ElevenLabs E2E French tests (recommended)
- `language_tests/french_full_elevenlabs/` - Larger legacy suite (optional)
- `_cache_tts/` - TTS cache

**Refresh derived fields (duration, etc.):**
```bash
python scripts/refresh_audio_metadata.py
```

## Add / Mark a WAV

Register a hand-made/generated WAV in the metadata registry:

```bash
python scripts/add_audio_test_case.py --suite e2e_french --group positive --file <path.wav> --full-phrase "Alexa. ..." --command "..." --intent play_music --parameters '{"query":"..."}'
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
