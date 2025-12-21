# CLAUDE.md - Pi-Sat Developer Guide

**AI Development Reference** - Optimized for Claude Code

**Communication Style:** Short, synthetic answers. Use checklists. No verbose summaries.

---

## ⚡ Development Environment

**Development happens directly on production hardware:**
- Raspberry Pi 5 (8GB)
- Hailo-8L AI accelerator
- USB microphone with hardware mute button
- Speaker output
- No separate dev/prod environments - code runs where it's written

---

## Quick Reference (Always Scan This)

### Project Essence
Pi-Sat: **Local-first, offline voice-controlled music player** for kids on Raspberry Pi 5 + Hailo-8L.
- Zero cloud dependencies, 100% on-device processing
- Target: Kids controlling music ("Play Frozen!", "I love this!", "Stop in 30 minutes")
- Philosophy: KISS (Keep It Simple, Stupid) - minimal, elegant code

### Architecture Flow
```
Wake Word ("Alexa") → Orchestrator (lifecycle) → CommandProcessor (pipeline) →
  1. Volume Duck
  2. VAD Recording
  3. Hailo Whisper STT (French/English configurable)
  4. Intent Engine (intent only)
  5. MusicResolver (query extraction + catalog match)
  6. MPD Controller → Music Playback
  7. Piper TTS Response
  8. Volume Restore

Alternative: Mic Mute Button (unmute) → Force Listening Mode
```

### Architecture Diagram
```
Main Application
└── Orchestrator (lifecycle manager)
    ├── WakeWordListener (detection)
    ├── TimeScheduler (bedtime enforcement)
    ├── MorningAlarm (wake-up alarms)
    ├── ActivityTracker (usage limits)
    └── CommandProcessor (command pipeline)
        ├── SpeechRecorder (VAD recording)
        ├── HailoSTT (speech-to-text)
        ├── IntentEngine (fuzzy classification)
        ├── MusicResolver (query extraction + catalog match)
        ├── MusicLibrary (catalog & search)
        ├── MPDController (playback control + queue + repeat/shuffle)
        ├── PiperTTS (text-to-speech)
        └── VolumeManager (volume control with limits)
```

### File Structure Map
```
pi-sat/
├── modules/                     # Core application modules
│   ├── interfaces.py            # Protocol definitions
│   ├── factory.py               # Dependency injection
│   ├── orchestrator.py          # Lifecycle manager
│   ├── command_processor.py     # Command pipeline
│   ├── music_library.py         # Catalog & search
│   ├── wake_word_listener.py    # openWakeWord + Hailo
│   ├── speech_recorder.py       # WebRTC VAD recording
│   ├── hailo_stt.py             # Hailo Whisper STT (singleton)
│   ├── intent_engine.py         # Fuzzy command classifier
│   ├── music_resolver.py        # Query extraction + catalog match
│   ├── mpd_controller.py        # MPD music control (+ queue, repeat, shuffle)
│   ├── piper_tts.py             # Offline TTS
│   ├── volume_manager.py        # Unified volume control
│   ├── time_scheduler.py        # Bedtime enforcement & quiet hours
│   ├── morning_alarm.py         # Wake-up alarms with gentle volume
│   ├── activity_tracker.py      # Daily time limits & usage tracking
│   ├── mic_mute_detector.py     # Audio level monitoring (planned)
│   ├── audio_player.py          # Wake sound playback
│   ├── audio_devices.py         # Device enumeration
│   ├── retry_utils.py           # Retry logic with exponential backoff
│   └── logging_utils.py         # Logging setup
├── tests/                       # 140+ tests, 20+ audio samples
├── scripts/                     # Utility scripts
│   ├── speak.py                 # Standalone TTS utility
│   ├── test_synthetic.py        # End-to-end pipeline test
│   ├── generate_language_test_audio.py  # Generate test audio
│   ├── generate_music_test_audio.py     # Generate bilingual (FR/EN) music STT suite
│   ├── qa_stt_audio_suite.py            # QA pauses + WAV format for generated suites
│   ├── benchmark_stt.py          # STT benchmark (Hailo/native, FR/EN)
│   ├── test_playlist.py         # MPD playlist testing
│   ├── player.py                # Interactive MPD player
│   └── test_volume.py           # Volume control debugging
├── docs/                        # Detailed documentation
│   ├── IMPLEMENTATION_PATTERNS.md  # Detailed patterns & code examples
│   ├── TESTING.md               # Testing strategies & patterns
│   ├── TROUBLESHOOTING.md       # Common issues & solutions
│   └── RESEARCH.md              # Research notes & decisions
├── resources/
│   ├── wakesound.wav
│   └── voices/                  # Piper TTS models
├── config.py                    # Central configuration
└── pi-sat.sh                    # Command shortcuts
```

### Component Registry
| Module | Purpose | Status | Details |
|--------|---------|--------|---------|
| **Architecture (Dec 2025)** | | | |
| interfaces.py | Protocol definitions | ✅ | Type-safe contracts |
| factory.py | Dependency injection | ✅ | Creates configured instances |
| command_processor.py | Command pipeline | ✅ | Fully testable |
| music_library.py | Catalog & phonetic search | ✅ | Hybrid search (90% accuracy) |
| **Core Modules** | | | |
| orchestrator.py | Lifecycle manager | ✅ | Delegates to CommandProcessor |
| wake_word_listener.py | "Alexa" detection | ✅ | Lazy PyAudio, resampling |
| speech_recorder.py | Voice recording | ✅ | Adaptive VAD (dual detection), stream-based |
| hailo_stt.py | Speech-to-text | ✅ | Singleton, retry logic, multilingual |
| intent_engine.py | Command classification | ✅ | thefuzz, priority-based |
| music_resolver.py | Query extraction + catalog match | ✅ | DDD bridge for play_music |
| mpd_controller.py | Music control | ✅ | Queue, repeat, shuffle, favorites |
| piper_tts.py | Text-to-speech | ✅ | Volume management, 0.3 RTF |
| volume_manager.py | Volume control | ✅ | Ducking, MPD/ALSA, limits |
| **Kid Safety Features (NEW)** | | | |
| time_scheduler.py | Bedtime enforcement | ✅ | Quiet hours, warnings |
| morning_alarm.py | Wake-up alarms | ✅ | Gentle volume, recurring |
| activity_tracker.py | Usage limits | ✅ | Daily time tracking, warnings |

### Current Status (Updated: 2025-12-19)
**✅ Complete:**
- **Multi-language system** (English/French bilingual, no translation, 400+ trigger phrases)
- **Phonetic music search** (French→English matching, Beider-Morse, 90% accuracy)
- Language detection (French/English configurable via `HAILO_STT_LANGUAGE`)
- Architecture refactoring (Protocol interfaces, factory pattern)
- Wake word detection (openWakeWord)
- Speech recording (WebRTC VAD + adaptive energy-based detection)
- Hailo STT (whisper-base, multilingual)
- Intent engine (language-aware, fuzzy matching, priority-based, **4 active intents** in production)
- MPD controller (play/pause/skip/volume/favorites/sleep timer/queue/repeat/shuffle)
- VolumeManager (unified music/TTS volume, ducking, max volume limits)
- Piper TTS (French voice, volume management)
- Error recovery (retry logic, exponential backoff)
- Test infrastructure (140+ tests, 20+ audio samples)

**✅ Kid Safety Features (NEW - 2025-12-15):**
- Bedtime enforcement (quiet hours with warnings)
- Morning alarms (gentle wake-up with music)
- Daily time limits (usage tracking with warnings)
- Volume limits (max volume cap for kid safety)
- Queue management (play next, add to queue)
- Repeat/shuffle modes (single song, playlist, shuffle)

**📋 Next:**
- Factory integration for new modules
- Tests for new features
- Mic mute detector
- End-to-end hardware testing

### Common Commands
```bash
# Running
./pi-sat.sh run              # Normal mode
./pi-sat.sh run_debug        # Debug with audio playback
./pi-sat.sh test_synthetic   # End-to-end pipeline test

# Testing & Calibration
./pi-sat.sh test             # All tests
./pi-sat.sh test wake_word   # Specific component
./pi-sat.sh test_wake_stt    # Wake word → STT feedback loop
./pi-sat.sh calibrate_vad    # Calibrate adaptive VAD thresholds
pytest tests/test_language_detection.py -v  # Language tests

# MPD
./pi-sat.sh mpd_start        # Start MPD daemon
./pi-sat.sh mpd_update       # Update music library
./pi-sat.sh mpd_status       # Check status

# Utilities
./pi-sat.sh hailo_check      # Hailo diagnostics
./pi-sat.sh completion       # Enable bash completion
python scripts/speak.py "Hello world"  # Test TTS
python scripts/player.py     # Interactive player
```

---

## Configuration

### Essential Settings (config.py)
```python
# Audio
RATE = 48000              # Device sample rate
SAMPLE_RATE = 16000       # Model expected rate
CHUNK = 320               # Bytes per chunk

# Wake Word
WAKE_WORD_MODEL = "alexa_v0.1"
WAKE_WORD_THRESHOLD = 0.5
WAKE_WORD_COOLDOWN = 2.0

# VAD (Voice Activity Detection)
VAD_LEVEL = 2                    # WebRTC VAD sensitivity (0-3, 3=most aggressive)
SILENCE_THRESHOLD = 1.0          # Seconds of silence to mark command end
MAX_RECORDING_TIME = 10.0        # Maximum seconds to record

# Adaptive VAD (Energy-based detection)
# Tune these based on your environment (use ./pi-sat.sh calibrate_vad)
VAD_SPEECH_MULTIPLIER = 1.3      # Speech energy multiplier vs noise floor
                                  # 1.3 = noisy environment, 2.0 = quiet environment
VAD_SILENCE_DURATION = 1.2       # Seconds of silence to end recording (0.8-1.5s)
VAD_MIN_SPEECH_DURATION = 0.5    # Minimum speech duration in seconds

# STT (Hailo Whisper)
HAILO_STT_MODEL = "whisper-base"
HAILO_STT_LANGUAGE = "fr"  # Language: 'fr', 'en', 'es', etc.
STT_MAX_RETRIES = 3
STT_RETRY_DELAY = 0.5
STT_RETRY_BACKOFF = 2.0

# MPD
MPD_HOST = "localhost"
MPD_PORT = 6600
MUSIC_LIBRARY = "~/Music/pisat"

# TTS (Piper)
PIPER_MODEL_PATH = "resources/voices/fr_FR-siwis-medium.onnx"
PIPER_BINARY = "/usr/local/bin/piper"
PIPER_OUTPUT_DEVICE = "default"
TTS_VOLUME = 80

# Intent Engine
FUZZY_MATCH_THRESHOLD = 50  # 0-100

# Volume Control
VOLUME_DUCK_LEVEL = 20      # Duck music to 20% during voice input
VOLUME_STEP = 10            # Volume change step
MAX_VOLUME = 80             # Maximum volume for kid safety

# Kid Safety & Parental Control
BEDTIME_ENABLED = true
BEDTIME_START = "21:00"     # Quiet time start (24h format)
BEDTIME_END = "07:00"       # Quiet time end (24h format)
BEDTIME_WARNING_MINUTES = 10  # Warn X minutes before bedtime

# Activity Time Limits
DAILY_TIME_LIMIT_ENABLED = false  # Enable daily listening limits
DAILY_TIME_LIMIT_MINUTES = 120     # Max minutes per day
TIME_LIMIT_WARNING_MINUTES = 10    # Warn when X minutes left

# Morning Alarm
ALARM_ENABLED = true
ALARM_GENTLE_WAKEUP_DURATION = 300  # 5 min gradual volume increase
ALARM_START_VOLUME = 10             # Start gentle wake at 10%
ALARM_END_VOLUME = 50               # End gentle wake at 50%

# Playback Mode defaults
DEFAULT_REPEAT_MODE = "off"         # off, single, playlist
DEFAULT_SHUFFLE_MODE = false
```

### Environment Overrides (.envrc.local)
**Note:** Default language is **French**. Only override if needed.

```bash
# .envrc is minimal (venv + PYTHONPATH only)
# All app config lives in config.py
# Use .envrc.local for machine-specific overrides:

export HAILO_STT_LANGUAGE='en'    # Switch to English (default: fr)
export PISAT_DEBUG=true            # Enable debug mode
export PISAT_MUSIC_DIR="/custom/path"  # Custom music directory

# Adaptive VAD tuning (optional - tune via calibration)
export VAD_SPEECH_MULTIPLIER=1.5   # Adjust sensitivity
export VAD_SILENCE_DURATION=1.0    # Faster/slower end detection
```

---

## Adaptive VAD

**Dual detection** - WebRTC + energy-based (both must agree)
**Auto-calibration** - Noise floor measured at startup
**Tunable** - Multiplier 1.3-2.0 based on SNR

```bash
./pi-sat.sh calibrate_vad  # Get recommended settings
```

See [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for tuning guide.

---

## Multi-Language

**Bilingual** - EN/FR with 400+ trigger phrases (22 intents defined, 4 active in production)
**Zero translation** - Separate pattern dicts, shared fuzzy logic
**Default:** French (set `HAILO_STT_LANGUAGE='en'` for English)
**Production Scope:** Only 4 essential intents active (play_music, stop, volume_up, volume_down) - keeping it simple for kids

---

## Phonetic Music Search

**90% accuracy** - Hybrid phonetic (Beider-Morse 60% + text fuzzy 40%)
**100% match rate** - Always returns best match with confidence warnings

See [PHONETIC_SEARCH_ARCHITECTURE.md](docs/PHONETIC_SEARCH_ARCHITECTURE.md) for details.

---

## Implementation Patterns

See [IMPLEMENTATION_PATTERNS.md](docs/IMPLEMENTATION_PATTERNS.md) for code examples.

**Key:** Wake word (lazy init), VAD (dual detection), STT (singleton + retry), Intent (multilingual + priority), MPD (reconnect), Volume (duck/restore), TTS (0.3 RTF)

---

## Testing

**For comprehensive testing guide, see [docs/TESTING.md](docs/TESTING.md)**

### Quick Test Reference
```bash
# All tests (140+ tests)
pytest tests/ -v

# Component tests
pytest tests/test_intent_engine.py -v  # 30 tests
pytest tests/test_mpd_controller.py -v  # 33 tests

# Language detection (requires Hailo)
pytest tests/test_language_detection.py -v -s

# Integration tests
pytest tests/test_integration_full_pipeline.py -v  # 12 tests

# Generate test audio
python scripts/generate_language_test_audio.py
```

### Test Coverage
- **Code coverage**: >85%
- **Total tests**: 140+
- **Audio samples**: 20+ (French/English generated with Piper TTS)
- **Integration tests**: 12 full pipeline tests

---

## Voice Commands Supported

**ACTIVE IN PRODUCTION (4 Commands):**

### Music Control ✅
- "Play [song/artist name]" - Fuzzy search and play

### Playback Control ✅
- "Stop" - Stop playback

### Volume Control ✅
- "Louder" / "Volume up" - Increase by 10%
- "Quieter" / "Volume down" - Decrease by 10%
- *(Auto-limited to MAX_VOLUME for kid safety)*

**AVAILABLE BUT DISABLED (18 Additional Commands):**
All patterns defined in intent_engine.py but set to inactive via `ACTIVE_INTENTS`:
- Pause/Resume - Pause playback
- Skip/Next - Next track
- Previous/Back - Previous track
- Play favorites - Play favorites.m3u
- "I love this" - Add to favorites
- "Stop in [X] minutes" - Sleep timer
- Repeat/Shuffle modes
- Queue management (play next, add to queue)
- Morning alarms (set/cancel alarm)
- Bedtime scheduling
- Time limit tracking

**To enable additional intents:** Edit `ACTIVE_INTENTS` in `modules/intent_engine.py`

---

## Troubleshooting

**For detailed troubleshooting, see [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)**

### Quick Fixes

**Hailo not detected:**
```bash
hailortcli fw-control identify
ps aux | grep python  # Check for zombie processes
kill <PID>  # Kill zombies
```

**MPD not starting:**
```bash
mpd --kill && mpd ~/.mpd/mpd.conf
mpc update && mpc status
```

**Wake word not detecting:**
```bash
./pi-sat.sh run_debug  # Check confidence scores
# Adjust WAKE_WORD_THRESHOLD in config.py
```

**Audio issues:**
```bash
arecord -l  # List input devices
aplay -l    # List output devices
amixer get Master  # Check volume
```

---

## Performance Benchmarks

| Component | Latency | Notes |
|-----------|---------|-------|
| Wake word detection | ~100ms | Continuous monitoring |
| VAD silence detection | 1.0s | Configurable threshold |
| Hailo STT | 1-2s | Depends on audio length |
| Intent classification | <1ms | Fuzzy matching |
| MPD command | <50ms | Network latency |
| Piper TTS | 0.3 RTF | 3× faster than real-time |
| **Total pipeline** | **2-4s** | Wake word → Music plays |

---

## Key Decisions & Rationale

**For detailed research notes, see [docs/RESEARCH.md](docs/RESEARCH.md)**

**Why No LLM for Intent?**
- Fast (<1ms), deterministic, no hallucinations
- Resource-efficient (no GPU beyond STT)
- Kid-friendly (simple commands better than natural language)

**Why MPD?**
- Rock-solid industry standard
- Low resource usage
- Headless, playlist support

**Why Piper TTS?**
- Best offline TTS quality
- Fast (0.3 RTF on Pi 5)
- Multiple voices, active development

**Why Fuzzy Matching (thefuzz)?**
- `token_set_ratio` handles extra words well
- Threshold 50 balances accuracy/coverage
- Priority system prevents ambiguities
- Sufficient speed for <1000 songs (switch to RapidFuzz if needed)

**Why French as Default?**
- Target deployment is French-speaking users
- Easily switched via `HAILO_STT_LANGUAGE` config
- Same model supports all languages (just token swap)

---

## Documentation Principles

### Purpose
Keep CLAUDE.md optimized for AI assistant performance while maintaining comprehensive documentation.

### Size Guidelines
- **Target:** 20-25k characters for optimal LLM performance
- **Current:** 20k characters ✅ (23% reduction from 26k)

### Recent Cleanup (2025-12-20)
- Archived 22 historical docs → `docs/archive/`
- Created `CHANGELOG.md`, `docs/README.md`, `.gitignore`
- CLAUDE.md: 26KB→20KB (removed redundant examples, kept links)
- Result: 5 root files, 10 docs files, clean repo

### Structure Rules
1. **CLAUDE.md (this file):** Essential info only
   - Quick reference (architecture, status, commands)
   - Configuration essentials
   - Brief pattern summaries with links
   - Quick troubleshooting tips
   - Links to detailed docs

2. **Detailed Documentation:** See `docs/` folder
   - `IMPLEMENTATION_PATTERNS.md`: Code examples & patterns
   - `TESTING.md`: Testing strategies & coverage
   - `TROUBLESHOOTING.md`: Detailed debugging steps
   - `RESEARCH.md`: Design decisions & benchmarks

### When to Split Content
**Move to separate docs when:**
- Section exceeds 200 lines
- Code examples are longer than necessary for quick reference
- Content is primarily reference material (full API docs, all test patterns)
- Information is useful but not essential for daily development

**Keep in CLAUDE.md when:**
- Information is needed for every coding session
- Quick reference is essential (architecture diagram, common commands)
- Configuration values developers need to know
- Status updates and recent changes

### Maintenance Protocol
**Before adding to CLAUDE.md:**
1. Check if it's essential for AI assistant context
2. Consider if it belongs in detailed docs instead
3. If adding, remove equivalent amount of less-critical content
4. Keep total size <30k characters

**After making changes:**
1. Check file size: `wc -c CLAUDE.md`
2. Verify links to detailed docs work
3. Update "Last Updated" timestamp
4. Test that essential info is still easily accessible

### Link Format
Use relative links to docs:
```markdown
[Detailed implementation patterns](docs/IMPLEMENTATION_PATTERNS.md)
```

---

## Documentation Index

**Full Navigation:** See **[docs/README.md](docs/README.md)** for complete documentation index

**Quick Links:**
- **[IMPLEMENTATION_PATTERNS.md](docs/IMPLEMENTATION_PATTERNS.md)** - Detailed code patterns and examples
- **[TESTING.md](docs/TESTING.md)** - Complete testing guide and coverage
- **[TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** - Problem-solving guide
- **[RESEARCH.md](docs/RESEARCH.md)** - Design decisions and benchmarks
- **[CHANGELOG.md](CHANGELOG.md)** - Version history and changes
- **[INSTALL.md](INSTALL.md)** - Full installation instructions

---

**Last Updated:** 2025-12-20

**Recent Updates:** See [CHANGELOG.md](CHANGELOG.md) for detailed version history and changes.

**Current Version:** 2.0.0
- Adaptive VAD system with dual detection
- Multi-language support (EN/FR)
- Kid safety features (bedtime, alarms, time limits)
- Phonetic music search

**Next Review:** After hardware testing on RPi 5

### E2E Tests (French)

**New:** Wake word → STT → Intent validation
**Audio:** ElevenLabs (10 positive + 3 negative)
**Generate:** `python scripts/generate_e2e_french_tests.py`
**Run:** `pytest tests/test_e2e_french.py -v`

See [E2E_FRENCH_TESTS_README.md](scripts/E2E_FRENCH_TESTS_README.md)
