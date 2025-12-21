# Pi-Sat Testing Strategy

**Comprehensive test suite for offline voice-controlled music player**

---

## Testing Philosophy

### Core Principles

1. **Honest Testing** - Never fake tests to pass. If a test fails, fix the underlying problem.
2. **Realistic Data** - Use real audio samples, real music files, real commands.
3. **Comprehensive Coverage** - Unit tests, integration tests, E2E tests, interactive tests.
4. **Reproducible** - Tests should produce consistent results across runs.
5. **Fast Feedback** - Quick unit tests, slower integration tests, optional manual tests.
6. **Self-Documenting** - Tests serve as documentation and usage examples.

### Test Pyramid

```
                  /\
                 /  \    Manual/Interactive Tests (5%)
                /____\   - User interaction tests
               /      \  - Hardware validation
              /________\
             /          \ E2E Functional Tests (15%)
            /____________\ - Full pipeline validation
           /              \ - Real audio → Real output
          /________________\
         /                  \ Integration Tests (30%)
        /____________________\ - Module interactions
       /                      \ - Component integration
      /________________________\
     /                          \ Unit Tests (50%)
    /____________________________\ - Individual modules
   /                              \ - Pure functions
  /________________________________\ - Edge cases
```

---

## Test Categories

### 1. Unit Tests (Fast, Isolated)

**Location:** `tests/test_*.py`

**Purpose:** Test individual modules in isolation with mocked dependencies.

**Modules to Test:**
- ✅ `test_piper_tts.py` - TTS module (DONE)
- `test_intent_engine.py` - Command classification
- `test_mpd_controller.py` - Music player control
- `test_wake_word_listener.py` - Wake word detection (EXISTS)
- `test_speech_recorder.py` - VAD recording (EXISTS)
- `test_hailo_stt.py` - STT transcription (EXISTS)
- `test_mic_mute_detector.py` - Mic mute detection

**Coverage Goals:**
- Code coverage: >80%
- Function coverage: 100%
- Branch coverage: >70%
- Error handling: All error paths tested

### 2. Integration Tests (Medium Speed)

**Location:** `tests/integration/`

**Purpose:** Test how modules work together.

**Test Scenarios:**
- Wake word → Recording pipeline
- Recording → STT → Intent classification
- Intent → MPD control → TTS response
- Volume ducking during recording
- Favorites management workflow
- Sleep timer with fade-out

### 3. E2E Functional Tests (Slower)

**Location:** `tests/e2e/`

**Purpose:** Test complete workflows from voice input to audio output.

**Test Scenarios:**
- "Play Frozen" → Music starts playing
- "Pause" → Music pauses
- "I love this" → Song added to favorites
- "Stop in 5 minutes" → Sleep timer activates
- Fuzzy search: "frozzen" finds "Frozen"
- Error handling: "Play nonexistent song" → Error message

### 4. Interactive Tests (Manual)

**Location:** `tests/interactive/`

**Purpose:** Validate with real user interaction.

**Test Kit Features:**
- Button press simulation
- Microphone recording validation
- Speaker output validation
- Audio quality assessment
- Latency measurement
- User experience testing

---

## Test Data Infrastructure

### Synthetic Audio Generation

**Purpose:** Generate realistic test audio without manual recording.

**Strategy:**
1. **Use Piper TTS** to generate voice commands
2. **Add background noise** for realism
3. **Vary pitch/speed** to simulate different speakers
4. **Create edge cases** (mumbling, overlapping speech)

**Generated Commands:**
```python
COMMANDS_TO_GENERATE = [
    # Music control
    "Play Frozen",
    "Play the Beatles",
    "Play my favorites",
    "Pause",
    "Stop",
    "Skip",
    "Next song",
    "Previous",
    "Go back",

    # Volume control
    "Louder",
    "Volume up",
    "Quieter",
    "Volume down",

    # Favorites
    "I love this",
    "Like this song",
    "Add to favorites",

    # Sleep timer
    "Stop in 30 minutes",
    "Stop in 15 minutes",
    "Sleep timer 60 minutes",

    # Fuzzy matching (typos)
    "Play frozzen",  # Typo
    "Play beatles",  # Missing "the"
    "Play favorits", # Typo

    # Edge cases
    "Play",  # No song name
    "Ummm play Frozen",  # Filler words
    "Could you play Frozen please",  # Polite
]
```

### Demo Music Library

**Purpose:** Realistic music library for testing MPD integration.

**Structure:**
```
tests/demo_music/
├── Disney/
│   ├── Frozen - Let It Go.mp3
│   ├── Frozen - Do You Want to Build a Snowman.mp3
│   ├── Moana - How Far I'll Go.mp3
│   └── Lion King - Circle of Life.mp3
├── The Beatles/
│   ├── Hey Jude.mp3
│   ├── Let It Be.mp3
│   ├── Yellow Submarine.mp3
│   └── Here Comes the Sun.mp3
├── Kids Songs/
│   ├── Baby Shark.mp3
│   ├── Wheels on the Bus.mp3
│   └── Old MacDonald.mp3
└── favorites.m3u  # Test favorites playlist
```

**Generation Method:**
- Use **silent MP3 files** with proper metadata (title, artist, album)
- Or use **royalty-free music** from sources like:
  - Incompetech (Kevin MacLeod)
  - Free Music Archive
  - YouTube Audio Library
- Or generate **synthetic music** using tools like:
  - `ffmpeg` to create tone sequences
  - `sox` to synthesize simple melodies

### Audio Test Samples

**Already Exist:** `tests/audio_samples/`
- ✅ Wake word samples (8 positive, 8 negative)
- ✅ Command samples (simple, complex, with pauses)
- ✅ Integration samples
- ✅ E2E samples
- ✅ Noise samples

**To Add:**
- Generated synthetic commands (using Piper)
- Music playback validation samples
- TTS response validation samples

---

## Test Implementation Plan

### Phase 1: Module Unit Tests ✅ (Partially Done)

**Status:**
- ✅ Piper TTS tests (13 test cases)
- ✅ Wake word tests (existing)
- ✅ Speech recorder tests (existing)
- ✅ Hailo STT tests (existing)

**To Implement:**
- Intent Engine tests
- MPD Controller tests
- Mic mute detector tests

### Phase 2: Synthetic Test Data

**Generators to Build:**
1. **Voice Command Generator** (`tests/utils/generate_commands.py`)
   - Uses Piper TTS to create voice commands
   - Saves as WAV files in `tests/audio_samples/synthetic/`

2. **Music Library Generator** (`tests/utils/generate_music.py`)
   - Creates silent MP3 files with proper metadata
   - Organizes into realistic directory structure

3. **Noise Generator** (`tests/utils/generate_noise.py`)
   - Creates background noise samples
   - Mixes noise with voice commands

### Phase 3: Integration Tests

**Test Suites:**
1. **Wake → Record → STT Pipeline**
2. **STT → Intent → Action Pipeline**
3. **MPD Control Integration**
4. **TTS Response Integration**
5. **Volume Ducking Integration**

### Phase 4: E2E Functional Tests

**Full Workflow Tests:**
1. "Play Frozen" end-to-end
2. "Pause" end-to-end
3. "I love this" end-to-end
4. Fuzzy search end-to-end
5. Error handling end-to-end

### Phase 5: Interactive Test Kit

**User Interaction Tests:**
1. Mic mute button test (audio level detection and force listening trigger)
2. Microphone validation (record and playback)
3. Speaker validation (test tones)
4. Latency measurement
5. Voice command test (speak → hear response)

---

## Test Infrastructure

### Test Utilities

**Location:** `tests/utils/`

**Utilities:**
- `audio_utils.py` - Audio file manipulation helpers
- `mpd_mock.py` - Mock MPD server for testing
- `test_helpers.py` - Common test fixtures
- `generate_commands.py` - Synthetic voice command generator
- `generate_music.py` - Demo music library generator
- `generate_noise.py` - Background noise generator

### Test Base Classes

**Location:** `tests/test_base.py`

**Classes:**
- `PiSatTestBase` - Base class with common setup/teardown
- `MockedTestCase` - Tests with mocked hardware
- `IntegrationTestCase` - Tests with real components
- `InteractiveTestCase` - Manual user interaction tests

### Test Configuration

**Location:** `tests/test_config.py`

**Settings:**
```python
# Test mode detection
RUNNING_IN_CI = os.getenv('CI') == 'true'
RUNNING_IN_PYTEST = 'pytest' in sys.modules

# Test data paths
TEST_AUDIO_DIR = 'tests/audio_samples'
SYNTHETIC_AUDIO_DIR = 'tests/audio_samples/synthetic'
DEMO_MUSIC_DIR = 'tests/demo_music'

# Test timeouts
UNIT_TEST_TIMEOUT = 5  # seconds
INTEGRATION_TEST_TIMEOUT = 30
E2E_TEST_TIMEOUT = 60

# Hardware availability
HAS_HAILO = check_hailo_available()
HAS_MICROPHONE = check_microphone_available()
HAS_SPEAKER = check_speaker_available()
HAS_MPD = check_mpd_available()
```

---

## Test Execution

### Running Tests

**Quick Unit Tests (Fast):**
```bash
pytest tests/ -v -m unit
# ~30 seconds
```

**Integration Tests (Medium):**
```bash
pytest tests/integration/ -v
# ~2-3 minutes
```

**E2E Tests (Slow):**
```bash
pytest tests/e2e/ -v
# ~5-10 minutes
```

**All Tests:**
```bash
pytest tests/ -v --cov=modules --cov-report=html
# ~10-15 minutes
```

**Interactive Tests (Manual):**
```bash
python tests/interactive/test_kit.py
# Manual interaction required
```

### Test Markers

**Pytest Markers:**
```python
@pytest.mark.unit           # Fast unit tests
@pytest.mark.integration    # Integration tests
@pytest.mark.e2e           # End-to-end tests
@pytest.mark.interactive   # Manual interactive tests
@pytest.mark.slow          # Slow tests (skip in quick runs)
@pytest.mark.requires_hailo  # Requires Hailo hardware
@pytest.mark.requires_audio  # Requires audio hardware
@pytest.mark.requires_mpd    # Requires MPD running
```

**Usage:**
```bash
# Only fast tests
pytest -m "unit and not slow"

# Skip hardware-dependent tests
pytest -m "not requires_hailo and not requires_audio"

# Only tests that can run in CI
pytest -m "not interactive"
```

---

## Test Coverage Goals

### Module Coverage

| Module | Unit Tests | Integration Tests | E2E Tests | Target Coverage |
|--------|-----------|-------------------|-----------|----------------|
| Piper TTS | ✅ 13 tests | Pending | Pending | 90% |
| Intent Engine | Pending | Pending | Pending | 95% |
| MPD Controller | Pending | Pending | Pending | 85% |
| Wake Word | ✅ 8 tests | ✅ Done | ✅ Done | 90% |
| Speech Recorder | ✅ 6 tests | ✅ Done | ✅ Done | 85% |
| Hailo STT | ✅ 5 tests | ✅ Done | ✅ Done | 80% |
| Orchestrator | ✅ 3 tests | ✅ Done | ✅ Done | 75% |

### Overall Goals

- **Code Coverage:** >85%
- **Function Coverage:** 100%
- **Branch Coverage:** >75%
- **Test Pass Rate:** 100% (no flaky tests)
- **Test Execution Time:** <15 minutes (full suite)

---

## Continuous Testing

### Pre-Commit Hooks

**Run before each commit:**
```bash
# Quick unit tests
pytest tests/ -m unit -x

# Code quality
flake8 modules/ tests/
black --check modules/ tests/
mypy modules/
```

### CI/CD Pipeline

**GitHub Actions (proposed):**
```yaml
name: Pi-Sat Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run unit tests
        run: pytest tests/ -m "unit and not requires_hailo"
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

---

## Test Documentation

### Test Case Template

**Format:**
```python
def test_feature_scenario(self):
    """
    Test: [Brief description]

    Given: [Initial state]
    When: [Action performed]
    Then: [Expected result]

    Coverage: [What this tests]
    Edge Cases: [Edge cases covered]
    """
    # Arrange
    setup_code()

    # Act
    result = action()

    # Assert
    assert result == expected
```

### Test Documentation

**Location:** `tests/README.md`

**Contents:**
- How to run tests
- How to add new tests
- Test data generation
- Troubleshooting guide
- Known issues

---

## Interactive Test Kit

### Test Kit Features

**Purpose:** Validate hardware and user experience.

**Components:**

1. **Microphone Test**
   - Record 5 seconds of audio
   - Play back for validation
   - Check levels and quality

2. **Speaker Test**
   - Play test tones
   - Validate frequency response
   - Check for distortion

3. **TTS Test**
   - Speak test phrases
   - User confirms intelligibility
   - Rate voice quality

4. **Wake Word Test**
   - User says "Alexa"
   - System confirms detection
   - Measure latency

5. **Full Command Test**
   - User says "Alexa, play Frozen"
   - System responds and plays
   - User confirms success

6. **Mic Mute Button Test** (if available)
   - Mute microphone using hardware button
   - Verify audio level drops to near-zero
   - Unmute microphone
   - Verify force listening mode triggers

**Interface:**
```python
class InteractiveTestKit:
    def run_all_tests(self):
        """Run complete interactive test suite"""

    def test_microphone(self):
        """Test microphone recording and playback"""

    def test_speaker(self):
        """Test speaker output"""

    def test_tts(self):
        """Test text-to-speech"""

    def test_wake_word(self):
        """Test wake word detection"""

    def test_full_command(self):
        """Test complete voice command"""

    def test_mic_mute_button(self):
        """Test mic mute button detection via audio levels"""
```

---

## Challenges and Improvements

### Current Challenges

1. **Hailo Dependency**
   - Many tests require Hailo hardware
   - Need better CPU fallback for CI

2. **Audio Hardware**
   - CI environments don't have audio devices
   - Need virtual audio devices for testing

3. **MPD Integration**
   - Tests need MPD running
   - Mock MPD server for unit tests

4. **Timing Issues**
   - VAD silence detection is timing-dependent
   - Need deterministic timing for tests

### Proposed Improvements

1. **Virtual Audio Devices**
   - Use `snd-aloop` (ALSA loopback)
   - Use `pulseaudio` virtual sinks
   - Record test audio without hardware

2. **Mock MPD Server**
   - Implement minimal MPD protocol
   - Return predictable responses
   - Enable testing without MPD

3. **Deterministic Tests**
   - Use fixed audio samples (no live recording)
   - Mock time-dependent functions
   - Freeze time in tests

4. **Parallel Testing**
   - Run independent tests in parallel
   - Reduce total test time
   - Use pytest-xdist

5. **Test Data Management**
   - Git LFS for large audio files
   - On-demand generation of test data
   - Cache generated data

---

## Questions for Better Coverage

### 🤔 Do We Need...?

1. **Demo Music Library**
   - Should I create silent MP3 files with metadata?
   - Or use real royalty-free music?
   - How many songs? (Currently planning ~15)

2. **Recorded Voice Commands**
   - Should I record real voice commands?
   - Or use synthetic Piper-generated commands?
   - Should we cover multiple accents/ages?

3. **Noise Samples**
   - Do we need various background noise types?
   - (TV, conversation, kitchen sounds, etc.)
   - Or is simple white noise sufficient?

4. **Performance Benchmarks**
   - Should we measure latency at each stage?
   - Set performance targets?
   - Track regression over time?

5. **Stress Testing**
   - Test with 1000+ songs in library?
   - Rapid command sequences?
   - Long-running sessions?

6. **Error Injection**
   - Deliberately corrupt audio files?
   - Simulate MPD crashes?
   - Test recovery mechanisms?

---

## Implementation Priorities

### High Priority (Do First)

1. ✅ Piper TTS unit tests (DONE)
2. 🔄 Intent Engine unit tests (NEXT)
3. 🔄 MPD Controller unit tests
4. 🔄 Synthetic voice command generator
5. 🔄 Demo music library generator

### Medium Priority (Do Soon)

6. Integration tests (STT → Intent → MPD)
7. E2E tests (full pipeline)
8. Interactive test kit
9. Test documentation

### Low Priority (Nice to Have)

10. Performance benchmarks
11. Stress tests
12. CI/CD pipeline setup
13. Code coverage reports

---

## Success Criteria

### How We Know Tests Are Working

✅ **All tests pass** - 100% pass rate
✅ **No flaky tests** - Consistent results across runs
✅ **Fast feedback** - Unit tests complete in <30s
✅ **Good coverage** - >85% code coverage
✅ **Realistic tests** - Use real audio, real music, real commands
✅ **Self-validating** - Tests catch real bugs, not just pass
✅ **Well-documented** - Easy to understand and extend

### Definition of Done

A test is "done" when:
- ✅ It tests real functionality (not mocked to pass)
- ✅ It has clear arrange/act/assert structure
- ✅ It includes edge cases
- ✅ It runs quickly (<5s for unit tests)
- ✅ It's documented with docstring
- ✅ It passes consistently
- ✅ It fails when code is broken

---

*Last Updated: 2025-12-14*
*Next Review: After Intent Engine and MPD Controller implementation*
