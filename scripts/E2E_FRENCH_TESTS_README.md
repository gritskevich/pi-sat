# French E2E Test Suite

End-to-end tests validating: Wake Word Detection → STT → Intent Classification

## Structure

```
tests/audio_samples/e2e_french/
├── positive/              # 10 tests with "Alexa" wake word
│   ├── 01_play_music.wav
│   ├── 02_play_music.wav
│   ├── 03_play_music.wav
│   ├── 04_play_music.wav
│   ├── 05_play_music.wav
│   ├── 06_play_music.wav
│   ├── 07_play_music.wav
│   ├── 08_play_music.wav
│   ├── 09_play_music.wav
│   └── 10_play_music.wav
├── negative/              # 3 tests WITHOUT wake word
│   ├── 01_no_wake_word.wav
│   ├── 02_no_wake_word.wav
│   └── 03_no_wake_word.wav
└── manifest.json          # Minimal metadata (generated, gitignored)

tests/audio_samples/test_metadata.json  # Full metadata (tracked)
```

## Test Phrases

**Structure:** Segment-based (like integration tests)
- "Alexa" spoken separately
- 0.3s silence added with sox
- Command spoken separately
- All concatenated: `Alexa + 0.3s silence + command`

### Positive (with "Alexa")
1. "Alexa" + [0.3s] + "Je veux écouter maman" → `play_music`
2. "Alexa" + [0.3s] + "Je veux écouter Louane" → `play_music`
3. "Alexa" + [0.3s] + "Je veux écouter Stromae" → `play_music`
4. "Alexa" + [0.3s] + "Je veux écouter On écrit sur les murs" → `play_music`
5. "Alexa" + [0.3s] + "Je veux écouter Alors on danse" → `play_music`
6. "Alexa" + [0.3s] + "Tu peux jouer maman" → `play_music`
7. "Alexa" + [0.3s] + "Tu peux jouer Louane" → `play_music`
8. "Alexa" + [0.3s] + "Tu peux jouer Stromae" → `play_music`
9. "Alexa" + [0.3s] + "Tu peux mettre On écrit sur les murs" → `play_music`
10. "Alexa" + [0.3s] + "Tu peux mettre Alors on danse" → `play_music`

### Negative (no wake word)
1. "Joue de la musique" → Should NOT trigger
2. "Tu peux mettre Frozen" → Should NOT trigger
3. "Mets Kids United" → Should NOT trigger

## Generation

**Requirements:**
- ElevenLabs API key
- `elevenlabs` Python package

**Setup:**
```bash
pip install elevenlabs
export ELEVENLABS_API_KEY='your_api_key_here'
```

**Generate:**
```bash
python scripts/generate_e2e_french_tests.py
```

**Output:**
- 10 positive test files (~30 seconds total)
- 3 negative test files (~10 seconds total)
- `tests/audio_samples/e2e_french/manifest.json` (generated, gitignored)
- `tests/audio_samples/test_metadata.json` (tracked, source of truth)

## Running Tests

**All E2E tests:**
```bash
export PISAT_RUN_HAILO_TESTS=1
pytest tests/test_e2e_french.py -v
```

**Specific test class:**
```bash
export PISAT_RUN_HAILO_TESTS=1
pytest tests/test_e2e_french.py::TestFrenchE2EMusic -v
pytest tests/test_e2e_french.py::TestFrenchE2ENegative -v
```

**With report:**
```bash
export PISAT_RUN_HAILO_TESTS=1
pytest tests/test_e2e_french.py::TestE2EStatistics -v -s
```

## Test Organization

### Class Structure
- `TestFrenchE2EMusic` - 10 tests validating complete pipeline
- `TestFrenchE2ENegative` - 3 tests validating no false triggers
- `TestE2EStatistics` - Generate coverage report

### Each Test Validates
1. **Wake word detection** - "Alexa" detected in audio
2. **Command extraction** - Skip wake word, extract command
3. **STT transcription** - Hailo transcribes French correctly
4. **Intent classification** - IntentEngine matches correct intent
5. **Metadata-driven slicing** - Uses `tests/audio_samples/test_metadata.json` (`command_start_s`)

## Quality Metrics

**Target:**
- Wake word detection: 100% (10/10)
- STT accuracy: >80% (French)
- Intent classification: 100% (10/10)
- False positives: 0% (0/3 negative tests)

**Current:**
- Run tests to measure

## Audio Quality

**Generated with:**
- Voice: Sarah (French female, ElevenLabs voice ID: EXAVITQu4vr4xnSDxMaL)
- Model: `eleven_multilingual_v2`
- Format: WAV, 16kHz mono
- Structure: Segment-based (matches integration test approach)
  - "Alexa" segment generated separately
  - 0.3s silence created with sox
  - Command segment generated separately
  - All concatenated with sox

**Why segment-based:**
- Matches existing integration test patterns
- Clean separation of wake word and command
- Precise pause control (sox-generated)
- STT transcribes command cleanly (no wake word interference)

**Why ElevenLabs:**
- Higher quality than Piper TTS
- More realistic prosody and intonation
- Better wake word pronunciation
- Girl voice suitable for target use case

## Troubleshooting

**Audio not generated:**
```bash
# Check API key
echo $ELEVENLABS_API_KEY

# Generate
python scripts/generate_e2e_french_tests.py
```

**Tests fail:**
```bash
# Check Hailo device
hailortcli fw-control identify

# Run with debug
pytest tests/test_e2e_french.py -v -s
```

**Wake word not detected:**
- Check audio quality (should hear clear "Alexa")
- Verify wake word threshold in config.py
- Test with: `./pi-sat.sh run_debug`

## Maintenance

**Add new test:**
1. Add phrase to `E2E_TESTS` in `generate_e2e_french_tests.py`
2. Regenerate: `python scripts/generate_e2e_french_tests.py`
3. Tests are metadata-driven (no test code changes needed)

**Update voice/model:**
- Change `voice="Antoine"` or `model="..."` in generator
- Available voices: https://elevenlabs.io/voices

---

**Created:** 2025-12-20
**Status:** Ready for generation and testing
