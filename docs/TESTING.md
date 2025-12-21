# Testing Strategy

Comprehensive testing guide for Pi-Sat. This document explains test organization, patterns, and best practices.

**Quick Navigation:**
- [Test Organization](#test-organization)
- [Running Tests](#running-tests)
- [Test Patterns](#test-patterns)
- [Test Coverage Goals](#test-coverage-goals)
- [Integration Test Coverage](#integration-test-coverage)
- [Mocking Patterns](#mocking-patterns)
- [Language Detection Tests](#language-detection-tests)

---

## Test Organization

```
tests/
├── audio_samples/
│   ├── wake_word/positive/      # 8 "Alexa" samples
│   ├── wake_word/negative/      # 8 false positives
│   ├── commands/simple/         # "Play", "Pause", "Skip"
│   ├── commands/complex/        # "Play maman", "Stop in 30 minutes"
│   ├── commands/with_pauses/    # Pause detection validation
│   ├── integration/             # Full pipeline tests
│   ├── language_tests/          # ✨ Language detection tests
│   │   ├── french/              # 10 French audio files (basic suite, Piper TTS)
│   │   ├── french_full/         # 100+ French audio files (full suite, Piper TTS)
│   │   └── english/             # 10 English audio files (Piper TTS generated)
│   └── noise/                   # Background noise
├── demo_music/                  # Test MPD library
│   ├── Disney/
│   ├── The Beatles/
│   └── favorites.m3u
├── test_wake_word.py            # ✅ 8 tests
├── test_speech_recorder.py      # ✅ 6 tests
├── test_hailo_stt_suite.py      # ✅ 5 tests
├── test_piper_tts.py            # ✅ 13 tests
├── test_tts_integration.py     # ✅ 11 tests (TTS orchestrator integration)
├── test_volume_manager.py       # ✅ 22 tests (volume control, ducking, ALSA/MPD)
├── test_volume_integration.py   # ✅ 8 tests (orchestrator/TTS integration)
├── test_intent_engine.py        # ✅ 30 tests (fuzzy matching, classification)
├── test_mpd_controller.py      # ✅ 33 tests
├── test_language_detection.py   # ✅ 3 tests (French/English STT language detection)
├── test_mic_mute_detector.py    # 📋 To implement
├── test_orchestrator_e2e.py     # ✅ 3 tests
└── test_integration_full_pipeline.py  # ✅ 12 tests (full pipeline integration)
```

---

## Running Tests

```bash
# All tests
pytest tests/ -v

# Fast unit tests only
pytest tests/ -v -m unit

# Specific component
pytest tests/test_intent_engine.py -v

# Language detection tests (requires Hailo device)
pytest tests/test_language_detection.py -v -s

# With coverage
pytest tests/ -v --cov=modules --cov-report=html

# Via pi-sat.sh
./pi-sat.sh test
./pi-sat.sh test wake_word
./pi-sat.sh test stt
```

Generate test audio:
```bash
# Language tests (Piper TTS)
python scripts/generate_language_test_audio.py

# E2E tests (ElevenLabs - requires API key)
export ELEVENLABS_API_KEY='your_key'
python scripts/generate_e2e_french_tests.py
```

---

## Test Patterns

### Unit Test Structure

```python
import unittest

class TestIntentEngine(unittest.TestCase):
    def setUp(self):
        self.engine = IntentEngine()

    def test_play_command(self):
        """Test: Play command classification

        Given: Text "play maman"
        When: classify_command() called
        Then: Returns ('play', high_confidence, {'query': 'maman'})
        """
        intent, conf, params = self.engine.classify("play maman")

        self.assertEqual(intent, 'play')
        self.assertGreater(conf, 0.8)
        self.assertEqual(params['query'], 'maman')

    def test_fuzzy_matching(self):
        """Test: Fuzzy matching handles typos"""
        intent, conf, params = self.engine.classify("play mamann")

        self.assertEqual(intent, 'play')
        self.assertEqual(params['query'], 'mamann')  # Typo preserved
```

### Integration Test Pattern

```python
def test_wake_to_intent_pipeline(self):
    """Test: Wake word → STT → Intent pipeline"""
    # Load wake word audio
    audio = load_test_audio('wake_word/positive/alexa_001.wav')

    # Simulate pipeline
    detected = wake_word_listener.detect(audio)
    self.assertTrue(detected)

    # Load command audio
    command = load_test_audio('commands/simple/play.wav')
    text = hailo_stt.transcribe(command)

    # Classify
    intent, conf, params = intent_engine.classify(text)
    self.assertEqual(intent, 'play')
```

### Full Pipeline Integration Tests

```python
def test_play_music_command(self):
    """Test: Complete pipeline from audio file to MPD execution"""
    # Load synthetic audio file
    audio_file = "synthetic/music_control/01_play_maman.wav"

    # Test full pipeline: Wake Word → VAD → STT → Intent → MPD → TTS
    success = self._test_full_pipeline(
        audio_file=audio_file,
        expected_intent="play_music",
        expected_mpd_call="play"
    )

    self.assertTrue(success, "Play music pipeline should succeed")
    self.assertTrue(self.mock_mpd.play.called, "MPD play should be called")
```

---

## Test Coverage Goals

- **Code coverage**: >85%
- **Function coverage**: 100%
- **Branch coverage**: >75%
- **Test pass rate**: 100% (no flaky tests)

---

## Integration Test Coverage

### Full Pipeline Integration Tests

**File:** `test_integration_full_pipeline.py`

**Coverage:**
- ✅ **12 comprehensive tests** covering complete pipeline
- **Core Voice Commands** (7 tests):
  - Play music, pause, skip/next
  - Volume up/down
  - Add to favorites, sleep timer
- **Component Integration** (2 tests):
  - Volume ducking during voice input
  - TTS response after intent execution
- **Error Handling** (3 tests):
  - No intent match handling
  - Empty transcription handling
  - Fuzzy matching with typos

**Test Architecture:**
- **Real components**: Wake word, VAD, STT (when available), Intent engine
- **Mocked dependencies**: MPD, TTS (to avoid external requirements)
- **Graceful degradation**: Works without Hailo device (uses mock transcription)
- **Comprehensive validation**: Verifies each pipeline stage

---

## Mocking Patterns

### Mock MPD for Testing

```python
from unittest.mock import Mock, MagicMock

def test_mpd_play(self):
    mock_client = Mock()
    controller = MPDController(host='localhost', port=6600)
    controller.client = mock_client

    controller.play("frozen")

    mock_client.clear.assert_called_once()
    mock_client.add.assert_called()
    mock_client.play.assert_called_once()
```

### Mock Piper TTS

```python
def test_tts_speak(self):
    with patch('subprocess.run') as mock_run:
        tts = PiperTTS('/path/to/model.onnx')
        tts.speak("Hello")

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertIn('echo "Hello"', args)
        self.assertIn('piper', args)
```

---

## Language Detection Tests

**File:** `test_language_detection.py`

**Purpose:** Test Hailo STT language detection with real French and English audio generated by Piper TTS.

**Test Audio Generation:**
```bash
# Generate test audio files (10 French + 10 English)
python scripts/generate_language_test_audio.py
```
Requirements: Piper voice models present in `resources/voices/` and `sox` installed (used to resample to 16 kHz mono).

**Running Language Tests:**
```bash
# Test French STT
pytest tests/test_language_detection.py::TestLanguageDetection::test_french_audio_with_french_stt -v -s

# Test English STT
pytest tests/test_language_detection.py::TestLanguageDetection::test_english_audio_with_english_stt -v -s
```

**Test Coverage:**
- ✅ **3 tests** for language detection
  - French audio → French STT (80% accuracy)
  - English audio → English STT
  - Language mismatch detection (informational)

**Success Criteria:**
- Minimum 60% keyword match rate (allows for TTS/STT imperfections)
- Real Hailo transcription (no mocking)
- Comprehensive keyword matching per phrase

**Example Test Results:**
```
French Audio → French STT
==========================
✅ Bonjour, comment l'il vous?     → Matched (keywords: bonjour, comment)
✅ Merci beaucoup pour votre aide. → Matched (keywords: merci, beaucoup)
✅ Arrête la musique.              → Matched (keywords: arrête, musique)
❌ mais en pose.                   → No match (expected: pause)

Result: 8/10 (80% success rate)
```

---

## Music STT Audio Suite (FR/EN)

**Generator:** `scripts/generate_music_test_audio.py`

```bash
# Generate French music command fixtures (wake + mid-phrase pauses)
python scripts/generate_music_test_audio.py --languages fr --clean

# Verify sample rate + expected pause placement
python scripts/qa_stt_audio_suite.py --dir tests/audio_samples/integration/fr
```

## Best Practices

### Test Isolation
- Each test should be independent
- Use setUp/tearDown for resource management
- Clean up temporary files
- Reset mocks between tests

### Test Naming
- Use descriptive names: `test_play_command_with_fuzzy_match`
- Follow pattern: `test_<what>_<condition>_<expected_result>`
- Add docstrings with Given/When/Then format

### Test Organization
- Group related tests in classes
- Use `@unittest.skip` for temporarily disabled tests
- Mark slow tests with `@pytest.mark.slow`
- Use fixtures for shared setup

### Assertions
- Prefer specific assertions: `assertEqual` over `assertTrue`
- Include helpful failure messages
- Test both success and failure paths
- Validate error handling

### Continuous Integration
- All tests must pass before merge
- Run full test suite on every commit
- Check code coverage trends
- No flaky tests allowed

---

**See also:**
- [IMPLEMENTATION_PATTERNS.md](./IMPLEMENTATION_PATTERNS.md) - Implementation patterns and examples
- [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) - Common test failures and fixes
- [RESEARCH.md](./RESEARCH.md) - Research notes on testing approaches
