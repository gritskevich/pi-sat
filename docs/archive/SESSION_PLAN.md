# Pi-Sat Development Session Summary & Next Steps

**Session Date:** 2025-12-13
**Session Focus:** Architecture redesign, dependency installation, research
**Status:** Ready for Implementation Phase

---

## ✅ Session Accomplishments

### 1. Complete Architecture Redesign
- **Removed:** Home Assistant integration
- **Removed:** LED Controller (user decision - not implementing)
- **Removed:** Physical button via GPIO (replaced with mic mute detection)
- **Designed:** New music player architecture using MPD + Piper TTS + Fuzzy matching

### 2. Dependencies Successfully Installed

#### System Packages (via apt)
```bash
✅ mpd                   # Music Player Daemon
✅ mpc                   # MPD command-line client
✅ portaudio19-dev       # PyAudio dependency
✅ libasound2-dev        # ALSA development libraries
✅ alsa-utils            # ALSA utilities
✅ ffmpeg                # Audio/video processing
✅ sox + libsox-fmt-all  # Sound eXchange audio tools
✅ python3-pip/dev/venv  # Python development tools
✅ direnv                # Environment variable management
✅ git                   # Version control
```

#### Piper TTS Installation
```bash
✅ Binary: /usr/local/bin/piper (v1.2.0)
✅ Libraries: /usr/local/lib/*.so*
✅ Data: /usr/local/share/espeak-ng-data
✅ Symlink: /usr/share/espeak-ng-data -> /usr/local/share/espeak-ng-data
✅ Voice Model: ~/pi-sat/resources/voices/en_US-lessac-medium.onnx (61MB)
```

**Tested Successfully:**
```bash
$ echo "Hello from Piper" | piper --model ~/pi-sat/resources/voices/en_US-lessac-medium.onnx --output-raw > /tmp/test.raw
Output: 64,628 bytes
Real-time factor: 0.30 (generates speech 3x faster than real-time!)
```

### 3. Comprehensive Research Completed

**MPD & python-mpd2 Research:**
- ✅ Connection management patterns (persistent with reconnection wrapper)
- ✅ Command execution best practices
- ✅ Search methods (find vs search)
- ✅ Playlist management
- ✅ Event/idle notification patterns
- ✅ Common pitfalls and solutions

**Fuzzy Matching Research:**
- ✅ TheFuzz library scoring methods (ratio, token_sort_ratio, token_set_ratio)
- ✅ Best algorithms for music search (token_sort_ratio with 75-85 threshold)
- ✅ RapidFuzz vs TheFuzz comparison
- ✅ Combined scoring patterns

### 4. Documentation Created/Updated

| File | Status | Description |
|------|--------|-------------|
| ARCHITECTURE.md | ✅ Complete | Full technical design with data flow diagrams |
| INSTALL.md | ✅ Updated | Verified installation steps with actual commands |
| PROGRESS.md | ✅ Created | Detailed progress tracking |
| SESSION_PLAN.md | ✅ Created | This file - session summary and next steps |
| CLAUDE.md | ✅ Updated | Developer guide with new architecture |
| README.md | ✅ Updated | User-facing documentation |
| .envrc | ✅ Updated | direnv configuration for MPD/TTS/button |
| config.py | ✅ Updated | Added MPD, TTS, fuzzy matching, button settings |
| requirements.txt | ✅ Updated | Added python-mpd2, thefuzz, pytest |

### 5. Git Repository Setup
- ✅ Configured SSH key for GitHub
- ✅ Changed remote from HTTPS to SSH
- ✅ Force pushed to overwrite remote main branch
- ✅ Repository: https://github.com/gritskevich/pi-sat

---

## 📋 Next Session Implementation Plan

### Phase 1: Core Modules Implementation

#### Module 1: Piper TTS Wrapper (Simplest - Start Here)
**File:** `modules/piper_tts.py`

**Purpose:** Wrap Piper TTS binary for easy text-to-speech

**Key Features:**
- Simple subprocess call to `/usr/local/bin/piper`
- Output raw PCM audio
- Pipe to `aplay` for playback
- Response templates for common messages
- Error handling for missing voice model

**Interface:**
```python
class PiperTTS:
    def __init__(self, model_path=None, device='plughw:0,0'):
        """Initialize TTS with voice model and audio device"""

    def speak(self, text):
        """Generate and play speech"""

    def generate_audio(self, text):
        """Generate audio without playing (for testing)"""
```

**Test File:** `tests/test_piper_tts.py`
- Test initialization
- Test speech generation
- Test error handling (missing model)
- Test response templates

**Estimated Time:** 1-2 hours

---

#### Module 2: Intent Engine (Medium Complexity)
**File:** `modules/intent_engine.py`

**Purpose:** Classify voice commands using fuzzy matching (no LLM)

**Key Features:**
- Command pattern matching with thefuzz
- Extract parameters (song names, numbers for timers)
- Return (intent, confidence, parameters) tuple
- Support all voice commands from requirements

**Supported Intents:**
- `play` - Play music (with optional song name)
- `pause` - Pause playback
- `skip` - Next track
- `previous` - Previous track
- `volume_up` - Increase volume
- `volume_down` - Decrease volume
- `like` - Add to favorites
- `favorites` - Play favorites playlist
- `sleep_timer` - Sleep timer with minutes parameter

**Interface:**
```python
def classify_command(text):
    """
    Classify voice command and extract parameters.

    Returns: (intent, confidence, params)
    Examples:
        "play frozen" -> ('play', 0.95, {'query': 'frozen'})
        "pause" -> ('pause', 1.0, {})
        "stop in 30 minutes" -> ('sleep_timer', 0.9, {'minutes': 30})
    """

def fuzzy_match_patterns(text, patterns):
    """Match text against pattern dictionary using thefuzz"""
```

**Test File:** `tests/test_intent_engine.py`
- Test each intent classification
- Test parameter extraction
- Test fuzzy matching tolerance
- Test edge cases (empty, gibberish)

**Estimated Time:** 2-3 hours

---

#### Module 3: MPD Controller (Most Complex)
**File:** `modules/mpd_controller.py`

**Purpose:** Control Music Player Daemon for music playback

**Key Features:**
- Persistent connection with reconnection wrapper
- Playback control (play, pause, skip, previous)
- Fuzzy music search (MPD search + thefuzz scoring)
- Volume control and ducking
- Favorites management (save to favorites.m3u)
- Sleep timer with fade-out
- Connection health monitoring

**Interface:**
```python
class MPDController:
    def __init__(self, host='localhost', port=6600):
        """Initialize MPD client with persistent connection"""

    def connect(self):
        """Connect to MPD with retry logic"""

    def _try_cmd(self, func, *args):
        """Wrap command with reconnection logic"""

    def play(self, query=None):
        """Play current or search and play by query"""

    def pause(self):
        """Pause playback"""

    def skip(self):
        """Next track"""

    def previous(self):
        """Previous track"""

    def set_volume(self, level):
        """Set volume 0-100"""

    def duck_volume(self, restore=False):
        """Lower to 10% or restore original"""

    def fuzzy_search(self, query):
        """Search library with fuzzy matching"""

    def add_to_favorites(self):
        """Add current song to favorites.m3u"""

    def play_favorites(self):
        """Play favorites playlist"""

    def sleep_timer(self, minutes):
        """Schedule stop with 30s fade-out"""

    def get_current_song(self):
        """Get currently playing song info"""

    def is_playing(self):
        """Check if music is playing"""
```

**Test File:** `tests/test_mpd_controller.py`
- Test connection and reconnection
- Test playback commands
- Test fuzzy search algorithm
- Test volume ducking
- Test favorites management
- Mock MPD responses for testing

**Estimated Time:** 4-5 hours

---

### Phase 2: Orchestrator Integration

**File:** `modules/orchestrator.py` (modify existing)

**Changes Needed:**
1. Import new modules (intent_engine, mpd_controller, piper_tts)
2. Initialize MPD controller and Piper TTS in `__init__`
3. Modify `_process_command()` to:
   - Duck volume before recording
   - Pass transcribed text to intent engine
   - Route intent to MPD controller
   - Speak response via Piper TTS
   - Restore volume after completion

**Test File:** Update `tests/test_orchestrator_e2e.py`
- Test full pipeline with new modules
- Mock MPD and Piper for testing

**Estimated Time:** 2-3 hours

---

### Phase 3: Mic Mute Button Detection

**File:** `modules/mic_mute_detector.py`

**Purpose:** Detect mic mute button press via audio level monitoring

**Approach:**
- Monitor microphone audio level continuously
- Detect sudden drop to near-zero (muted)
- Detect rise from zero (un-muted)
- Trigger force listening mode on un-mute

**Interface:**
```python
class MicMuteDetector:
    def __init__(self, threshold=0.01, callback=None):
        """Initialize detector with sensitivity threshold"""

    def start_monitoring(self):
        """Start audio level monitoring thread"""

    def stop_monitoring(self):
        """Stop monitoring"""

    def _monitor_loop(self):
        """Main monitoring loop"""

    def on_unmute(self):
        """Callback when un-mute detected"""
```

**Integration:** Call orchestrator's force listen mode when un-mute detected

**Estimated Time:** 2 hours

---

### Phase 4: MPD Configuration

**File:** `~/.mpd/mpd.conf`

**Steps:**
1. Create MPD directories (`~/Music/pisat`, `~/.mpd/playlists`)
2. Generate MPD configuration file
3. Start MPD daemon
4. Add test music files
5. Update MPD database
6. Verify playback works

**Script:** Consider adding `./pi-sat.sh setup_mpd` command

**Estimated Time:** 1 hour

---

## 📊 Implementation Timeline Estimate

| Phase | Task | Estimated Time |
|-------|------|----------------|
| 1.1 | Piper TTS module + tests | 1-2 hours |
| 1.2 | Intent Engine module + tests | 2-3 hours |
| 1.3 | MPD Controller module + tests | 4-5 hours |
| 2.0 | Orchestrator integration | 2-3 hours |
| 3.0 | Mic mute detection | 2 hours |
| 4.0 | MPD configuration + testing | 1 hour |
| **Total** | | **12-16 hours** |

**Recommended Approach:** Implement in order (Piper → Intent → MPD → Integration)

---

## 🔧 Environment Setup for Next Session

### Before Starting Implementation:

1. **Activate Virtual Environment:**
   ```bash
   cd ~/pi-sat
   source venv/bin/activate
   ```

2. **Install Python Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure MPD:**
   ```bash
   # Follow Step 10 in INSTALL.md
   mkdir -p ~/Music/pisat ~/.mpd/playlists
   # Create mpd.conf
   # Start MPD
   ```

4. **Add Test Music:**
   ```bash
   # Copy some MP3 files to ~/Music/pisat/
   mpc update
   mpc listall  # Verify
   ```

5. **Enable direnv (optional but recommended):**
   ```bash
   echo 'eval "$(direnv hook bash)"' >> ~/.bashrc
   source ~/.bashrc
   cd ~/pi-sat
   direnv allow
   ```

---

## 🎯 Definition of Done for Each Module

### Piper TTS Module
- [ ] Can speak text and play via ALSA
- [ ] Can generate raw audio without playing
- [ ] Handles missing voice model gracefully
- [ ] Has response templates for common messages
- [ ] All tests passing

### Intent Engine Module
- [ ] Classifies all supported commands correctly
- [ ] Extracts parameters (song names, timer minutes)
- [ ] Returns confidence scores
- [ ] Handles typos via fuzzy matching
- [ ] All tests passing

### MPD Controller Module
- [ ] Can connect to MPD with retry logic
- [ ] All playback commands work (play/pause/skip/previous)
- [ ] Fuzzy search finds songs even with typos
- [ ] Volume ducking works
- [ ] Favorites can be added and played
- [ ] All tests passing (with mocked MPD)

### Orchestrator Integration
- [ ] Full pipeline works: Wake word → STT → Intent → MPD → TTS
- [ ] Volume ducks during recording
- [ ] Speaks responses via Piper
- [ ] Handles errors gracefully
- [ ] Integration tests passing

---

## 📝 Key Design Decisions

### Architecture Decisions Made:
1. **No LED Controller** - User decided not to implement visual feedback
2. **No GPIO Button** - Using mic mute detection instead
3. **Fuzzy Matching Threshold** - 75-85 for music search
4. **TTS Real-time Factor** - Piper achieves 0.30 (excellent)
5. **MPD Connection Pattern** - Persistent with reconnection wrapper
6. **Fuzzy Algorithm** - token_sort_ratio for word order tolerance

### Implementation Principles:
- **KISS** - Keep It Simple, Stupid
- **Modular** - Each component independent and testable
- **Elegant** - Clean, readable code
- **No Overengineering** - Solve actual problems only
- **Test-Driven** - Write tests alongside implementation

---

## 🐛 Known Issues to Address

1. **Python Dependencies Not Installed Yet**
   - Need to run: `pip install -r requirements.txt` in venv

2. **MPD Not Configured**
   - Need to create `~/.mpd/mpd.conf`
   - Need to start MPD daemon
   - Need to add test music

3. **No Test Music in Library**
   - Need to copy some MP3 files to `~/Music/pisat/`

4. **Documentation Updated** ✅
   - Cleaned up ARCHITECTURE.md, INSTALL.md, README.md, CLAUDE.md
   - Removed LED ring and GPIO button sections
   - Replaced with mic mute detection approach

---

## 🚀 Quick Start for Next Session

```bash
# 1. Navigate to project
cd ~/pi-sat

# 2. Activate venv
source venv/bin/activate

# 3. Install Python packages
pip install -r requirements.txt

# 4. Start implementation with Piper TTS
# Create modules/piper_tts.py
# Create tests/test_piper_tts.py
# Implement and test

# 5. Run tests
pytest tests/test_piper_tts.py -v

# 6. Continue with Intent Engine, then MPD Controller
```

---

## 📚 Reference Documents

- **ARCHITECTURE.md** - Complete technical design
- **PROGRESS.md** - Detailed progress tracking
- **INSTALL.md** - Installation guide with verified steps
- **CLAUDE.md** - Developer reference for Claude
- **README.md** - User-facing documentation

---

## 💭 Notes for Future Development

- Consider RapidFuzz instead of thefuzz if library >1000 songs
- MPD idle/event pattern could enable real-time UI updates
- Sleep timer implementation needs careful threading
- Volume fade-out algorithm needs smooth interpolation
- Consider caching fuzzy search results for performance

---

**Session Summary:** Excellent progress! Architecture redesigned, all dependencies installed and tested, comprehensive research completed. Ready to begin module implementation in next session.

**Next Priority:** Implement Piper TTS module (simplest) to validate the implementation approach, then proceed with Intent Engine and MPD Controller.

---

*Last Updated: 2025-12-13 18:00 GMT*
