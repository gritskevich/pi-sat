# Speech-to-Intent Test Suite

Comprehensive testing framework for the **STT → Intent** pipeline with French audio samples.

## Quick Start

```bash
# Run all tests
python scripts/test_stt_intent.py

# Show only failures
python scripts/test_stt_intent.py --failures-only

# Verbose mode (all details)
python scripts/test_stt_intent.py --verbose

# Export results to JSON
python scripts/test_stt_intent.py --export results.json
```

## What It Tests

The test suite validates the complete pipeline:

```
Audio File (WAV) → Hailo STT → Transcription → Intent Engine → Intent Classification
```

**Test Coverage:**
- 100+ French audio samples
- 22 different intent types
- Real TTS-generated voice commands
- Complete parameter extraction

## Test Files

**Audio Directory:** `tests/audio_samples/language_tests/french_full/`
- 100+ WAV files with French voice commands

**Expected Results:** `tests/audio_samples/language_tests/french_full/expected_intents.json`
- JSON mapping filename → expected intent + parameters

**Example:**
```json
{
  "tu_peux_jouer_maman.wav": {
    "intent": "play_music",
    "params": {"query": "maman"}
  },
  "augmente_volume.wav": {
    "intent": "volume_up",
    "params": {}
  }
}
```

## Understanding Results

### Success Criteria

A test **passes** when:
1. **Intent matches** - Actual intent == Expected intent
2. **Parameters match** - Extracted parameters match expected values
   - `query`: Fuzzy match (handles variations)
   - `duration`, `time`: Exact match

### Failure Analysis

When a test fails, you'll see:
```
✗ FAIL: tu_peux_jouer_maman.wav
  STT:      'tu peux jouer mamann'
  Expected: play_music {'query': 'maman'}
  Actual:   play_music {'query': 'mamann'}
  Confidence: 0.95
```

**Questions to ask:**
1. **Is the STT transcription wrong?** → Audio quality issue or Hailo config
2. **Is the intent wrong?** → Intent engine pattern mismatch
3. **Are parameters wrong?** → Parameter extraction regex issue
4. **Should we accept this variation?** → Update expected results

### Common Failure Types

**1. STT Transcription Error**
```
STT: 'tu peux jouer mamane' (expected: 'tu peux jouer maman')
```
→ **Action:** Check audio quality, consider regenerating sample

**2. Intent Misclassification**
```
Expected: play_music
Actual:   play_favorites
```
→ **Action:** Check intent patterns, adjust priority or triggers

**3. Parameter Extraction**
```
Expected: {'query': 'maman'}
Actual:   {'query': 'mamane'}
```
→ **Action:** Usually acceptable (fuzzy search handles variations)

**4. No Intent Found**
```
Actual: unknown
```
→ **Action:** Check fuzzy threshold, add new pattern

## Hailo French-Only Optimization

**✅ Already Enabled!** The system forces French-only via:

```python
# config.py
HAILO_STT_LANGUAGE = 'fr'  # Default: French
```

This optimization:
1. Sets language token to `<|fr|>` during Whisper decoding
2. Guides the model to transcribe in French only
3. Improves accuracy and reduces confusion with other languages
4. Speeds up inference (no multilingual detection needed)

**How it works:**
- Hailo Whisper uses language tokens to guide transcription
- Token `<|fr|>` tells model: "expect French audio, output French text"
- This is Whisper's standard optimization for single-language use

**To switch languages:**
```bash
# .envrc.local
export HAILO_STT_LANGUAGE='en'  # English
export HAILO_STT_LANGUAGE='es'  # Spanish
# etc.
```

## Adjusting Thresholds

### Fuzzy Match Threshold

Controls how similar text must be to match a pattern:

```bash
# More lenient (accept more variations)
python scripts/test_stt_intent.py --threshold 25

# More strict (require exact matches)
python scripts/test_stt_intent.py --threshold 50
```

**Current default:** 35 (optimized for phonetic matching)

### Language Configuration

Test with different languages:

```bash
# Test with English
python scripts/test_stt_intent.py --language en

# Test with French (default)
python scripts/test_stt_intent.py --language fr
```

## Output Format

### Console Output

```
📊 Running tests on 100 audio files...

[1/100] Testing: tu_peux_jouer_maman.wav... ✓ (95%)
[2/100] Testing: mets_pause.wav... ✓ (100%)
[3/100] Testing: joue_astronomiya.wav... ✗ (play_music)
...

================================================================================
📊 TEST SUMMARY
================================================================================
Total:  100
Passed: 87 (87.0%)
Failed: 13 (13.0%)

📋 FAILURE BREAKDOWN:
    5× play_music → unknown
    3× sleep_timer → stop
    2× play_next → play_music
    2× add_to_queue → play_music
    1× set_alarm → play_music
```

### JSON Export

```bash
python scripts/test_stt_intent.py --export results.json
```

**Output format:**
```json
{
  "summary": {
    "total": 100,
    "passed": 87,
    "failed": 13,
    "pass_rate": 87.0
  },
  "results": [
    {
      "filename": "tu_peux_jouer_maman.wav",
      "stt_transcription": "tu peux jouer maman",
      "expected_intent": "play_music",
      "actual_intent": "play_music",
      "expected_params": {"query": "maman"},
      "actual_params": {"query": "maman"},
      "confidence": 0.95,
      "success": true,
      "duration_ms": 1523
    }
  ]
}
```

## Interpreting Failures

### Decision Framework

For each failure, ask:

1. **Is the audio sample correct?**
   - Play the WAV file and verify it matches expected phrase
   - Check for noise, clarity, pronunciation

2. **Is the STT transcription acceptable?**
   - Minor variations OK: "tu peux jouer mamann" vs "tu peux jouer maman"
   - Major errors problematic: "joue" → "jeu"

3. **Is the intent classification correct?**
   - Consider user intent from transcription
   - May need to adjust expected results if STT changed meaning

4. **Should we update patterns or expected results?**
   - Update patterns → Change intent engine triggers/extraction
   - Update expected → Change expected_intents.json

### Action Matrix

| STT Good | Intent Good | Action |
|----------|-------------|--------|
| ✅ | ✅ | Update expected_intents.json (was wrong) |
| ✅ | ❌ | Update intent patterns or priority |
| ❌ | ✅ | Regenerate audio sample |
| ❌ | ❌ | Regenerate audio, then retest |

## Improving Test Coverage

### Adding New Test Cases

1. **Record/generate new audio:**
   ```bash
   python scripts/generate_music_test_audio.py --phrase "nouvelle phrase"
   ```

2. **Add to expected results:**
   ```json
   {
     "nouvelle_phrase.wav": {
       "intent": "play_music",
       "params": {"query": "nouvelle phrase"}
     }
   }
   ```

3. **Run tests:**
   ```bash
   python scripts/test_stt_intent.py
   ```

### Testing Specific Intents

Filter audio files by intent type:

```bash
# Test only play_music samples
ls tests/audio_samples/language_tests/french_full/joue_*.wav | wc -l

# Test only volume controls
ls tests/audio_samples/language_tests/french_full/*volume*.wav
```

## Troubleshooting

### Hailo Not Available

```
❌ Hailo STT not available - check hardware and models
```

**Fix:**
```bash
# Check Hailo hardware
hailortcli fw-control identify

# Check model files exist
ls hailo_examples/speech_recognition/hef/hailo8l/
```

### All Tests Failing

**Check language config:**
```bash
# Ensure French is configured
grep HAILO_STT_LANGUAGE config.py

# Check current language
python -c "from modules.hailo_stt import HailoSTT; stt = HailoSTT(); print(stt.get_language())"
```

### Low Pass Rate (<80%)

**Potential causes:**
1. Audio quality issues (regenerate samples)
2. Fuzzy threshold too strict (lower to 25-30)
3. Intent patterns need updating
4. Expected results outdated

## Best Practices

1. **Run tests after changes:**
   - After updating intent patterns
   - After changing fuzzy threshold
   - After Hailo model updates

2. **Review failures systematically:**
   - Group by failure type
   - Fix most common issues first
   - Update expected results when appropriate

3. **Track pass rate over time:**
   - Export results after changes
   - Compare pass rates
   - Aim for >90% pass rate

4. **Accept reasonable variations:**
   - "maman" vs "mamann" → OK (phonetic search handles it)
   - "joue" vs "jeu" → NOT OK (different meaning)

## Example Workflow

```bash
# 1. Run tests to get baseline
python scripts/test_stt_intent.py --export baseline.json

# 2. Review failures
python scripts/test_stt_intent.py --failures-only

# 3. Fix issues (update patterns, regenerate audio, etc.)
vim modules/intent_engine.py

# 4. Retest
python scripts/test_stt_intent.py --export after_fix.json

# 5. Compare results
python -c "import json; b=json.load(open('baseline.json')); a=json.load(open('after_fix.json')); print(f'Before: {b[\"summary\"][\"pass_rate\"]:.1f}%, After: {a[\"summary\"][\"pass_rate\"]:.1f}%')"
```

## Advanced Usage

### Custom Audio Directory

```bash
python scripts/test_stt_intent.py \
  --audio-dir /path/to/audio \
  --expected /path/to/expected.json
```

### Debug Mode

```bash
python scripts/test_stt_intent.py --debug
```

Shows:
- Hailo STT initialization details
- Intent matching process
- Full error traces

### Continuous Integration

```bash
#!/bin/bash
# Run tests and fail if pass rate < 90%

python scripts/test_stt_intent.py --export results.json

PASS_RATE=$(python -c "import json; r=json.load(open('results.json')); print(r['summary']['pass_rate'])")

if (( $(echo "$PASS_RATE < 90" | bc -l) )); then
  echo "❌ Pass rate too low: $PASS_RATE%"
  exit 1
else
  echo "✅ Pass rate acceptable: $PASS_RATE%"
  exit 0
fi
```

---

**Last Updated:** 2025-12-20
