# Pi-Sat Architecture Design

## Overview

Pi-Sat is a **local-first, offline voice-controlled music player** for kids, running on Raspberry Pi 5 with Hailo-8L AI accelerator. All processing happens on-device with zero cloud dependencies.

**Core Philosophy**: KISS (Keep It Simple, Stupid) - minimal, elegant code with no overcomplication.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      USER INTERACTION                        │
│   Wake Word ("Alexa") │ Voice Command │ Physical Button      │
└─────────────────────────────────────────────────────────────┘
                             │
┌────────────────────────────┼────────────────────────────────┐
│                     ORCHESTRATOR                              │
│                 (Central Coordinator)                         │
└───────────────────────────────────────────────────────────────┘
           │                │                │             │
┌──────────┴────┐  ┌────────┴──────┐  ┌─────┴─────┐
│ WAKE WORD     │  │ SPEECH        │  │ HAILO STT │
│ LISTENER      │  │ RECORDER      │  │ (Whisper) │
│               │  │               │  │           │
│ openWakeWord  │  │ WebRTC VAD    │  │ Hailo-8L  │
│ + Hailo accel │  │ Smart ducking │  │ Accelerate│
│               │  │               │  │           │
│ Detects       │  │ Records with  │  │ Transcribe│
│ "Alexa"       │  │ silence detect│  │ to text   │
└───────────────┘  └───────────────┘  └───────────┘
                             │
                    ┌────────┴────────┐
                    │ INTENT ENGINE   │
                    │ (Fuzzy Matcher) │
                    │                 │
                    │ thefuzz library │
                    │ Keyword mapping │
                    │ No LLM needed   │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
     ┌────────┴────┐  ┌──────┴──────┐  ┌───┴────────┐
     │ MPD CLIENT  │  │ PIPER TTS   │  │ MIC MUTE   │
     │             │  │             │  │ DETECTOR   │
     │ python-mpd2 │  │ Offline TTS │  │            │
     │ Music ctrl  │  │ en_US voice │  │ Audio level│
     │             │  │             │  │ monitoring │
     │ - Play      │  │ Speaks      │  │ - Detects  │
     │ - Pause     │  │ responses   │  │   mute     │
     │ - Skip      │  │             │  │ - Triggers │
     │ - Search    │  │             │  │   force    │
     │ - Volume    │  │             │  │   listen   │
     └─────────────┘  └─────────────┘  └────────────┘
              │
     ┌────────┴────────┐
     │ MPD (Daemon)    │
     │                 │
     │ Music Player    │
     │ Daemon          │
     │ - Manages queue │
     │ - Audio output  │
     │ - Database      │
     └─────────────────┘
              │
     ┌────────┴────────┐
     │ MUSIC LIBRARY   │
     │ ~/Music/pisat/  │
     │                 │
     │ Auto-ingested   │
     │ from USB        │
     └─────────────────┘
```

---

## Component Details

### 1. Wake Word Listener

**Status**: ✅ **Already Implemented**

- Uses openWakeWord with "alexa_v0.1" model
- Optional Hailo acceleration
- 48kHz → 16kHz resampling
- 2-second cooldown between detections
- Lazy PyAudio initialization

**Trigger Flow:**
```
Mic Audio → Resample → openWakeWord → Callback → Orchestrator
                                         ↓
                                    Volume: Duck to 10%
```

### 2. Speech Recorder

**Status**: ✅ **Already Implemented** (needs volume ducking enhancement)

- WebRTC VAD-based recording
- 1-second silence detection
- Max 10-second recording
- Debug mode for testing

**Enhancement Needed:**
- Add volume ducking integration (lower MPD volume when wake word detected)

### 3. Hailo STT (Speech-to-Text)

**Status**: ✅ **Already Implemented**

- Singleton pattern (one pipeline instance)
- Hailo-accelerated Whisper (whisper-base)
- CPU fallback for development
- Expects 16kHz audio input
- Fast inference (~1-2 seconds)

**No changes needed** - works perfectly for music commands.

### 4. Intent Engine (NEW)

**Status**: ❌ **To Be Implemented**

**Purpose**: Map voice commands to MPD actions without heavy LLM.

**Strategy**: Simple fuzzy matching + keyword extraction

```python
from thefuzz import fuzz, process

COMMAND_PATTERNS = {
    'play': ['play', 'start', 'resume', 'unpause'],
    'pause': ['pause', 'stop', 'halt'],
    'skip': ['skip', 'next', 'forward'],
    'previous': ['previous', 'back', 'rewind'],
    'volume_up': ['louder', 'volume up', 'increase volume'],
    'volume_down': ['quieter', 'volume down', 'decrease volume', 'lower'],
    'like': ['love this', 'like this', 'favorite', 'add to favorites'],
    'sleep': ['sleep timer', 'stop in', 'turn off in'],
}

def classify_command(text):
    """Returns (intent, confidence, extracted_params)"""
    # Example: "play frozen soundtrack" → ('play', 0.95, 'frozen soundtrack')
    # Example: "pause" → ('pause', 1.0, None)
    # Example: "stop in 30 minutes" → ('sleep', 0.9, '30')
```

**Fuzzy Music Search:**
```python
def fuzzy_find_song(query, music_library):
    """
    Finds best match using thefuzz.

    Example: "play frozzen" → finds "Frozen - Let It Go.mp3"
    Returns: (filename, score)
    If score < 50%, return None (no match)
    """
    from thefuzz import process
    titles = [extract_title(f) for f in music_library]
    best_match, score = process.extractOne(query, titles)
    return best_match if score >= 50 else None
```

### 5. MPD Client (NEW)

**Status**: ❌ **To Be Implemented**

**Dependencies:**
- `python-mpd2` library
- MPD daemon running (system service)

**Interface:**
```python
class MPDController:
    def __init__(self, host='localhost', port=6600):
        self.client = MPDClient()

    def play(self, query=None):
        """Play current or search and play"""

    def pause(self):
        """Pause playback"""

    def skip(self):
        """Next track"""

    def previous(self):
        """Previous track"""

    def set_volume(self, level):
        """0-100 volume"""

    def duck_volume(self, restore=False):
        """Lower to 10% or restore original"""

    def fuzzy_search_and_play(self, query):
        """Search library, find best match, play"""

    def add_to_favorites(self, current_song):
        """Append to favorites.m3u"""

    def sleep_timer(self, minutes):
        """Schedule stop with 30s fade"""
```

### 6. Piper TTS (NEW)

**Status**: ❌ **To Be Implemented**

**Purpose**: Speak responses (e.g., "Playing Frozen soundtrack", "I don't know that song")

**Dependencies:**
- `piper-tts` binary (https://github.com/rhasspy/piper)
- Voice model: `en_US-lessac-medium.onnx`

**Interface:**
```python
class PiperTTS:
    def __init__(self, model_path):
        self.model_path = model_path

    def speak(self, text, output_device='plughw:0,0'):
        """
        Generate speech and play via ALSA.

        Example:
        subprocess.run([
            'piper',
            '--model', self.model_path,
            '--output-raw',
            '|', 'aplay', '-D', output_device, ...
        ])
        """
```

**Response Templates:**
```python
RESPONSES = {
    'playing': "Playing {song_name}",
    'paused': "Paused",
    'skipped': "Skipping",
    'volume_up': "Volume up",
    'volume_down': "Volume down",
    'liked': "Added to favorites",
    'no_match': "I don't know that song",
    'sleep_timer': "I'll stop in {minutes} minutes",
}
```

### 7. Mic Mute Detector (NEW)

**Status**: ❌ **To Be Implemented**

**Purpose**: Detect hardware mic mute button state via analog audio level monitoring.

**Hardware**: USB microphone with hardware mute button (no GPIO required)

**Detection Method:**
- Continuously monitor microphone audio input levels
- Detect mute: audio level drops to near-zero (< 0.01 threshold)
- Detect unmute: audio level returns above threshold
- Trigger force listening mode when unmuted (bypasses wake word)

**Dependencies:**
- PyAudio (already installed)
- No additional hardware - uses existing microphone

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
        """Main monitoring loop - continuously checks audio levels"""

    def on_unmute(self):
        """Callback when unmute detected - triggers force listening"""
```

### 8. USB Auto-Ingest (NEW)

**Status**: ❌ **To Be Implemented**

**Purpose**: Automatically import music from USB sticks.

**Strategy**: udev rule triggers Python script.

**udev Rule** (`/etc/udev/rules.d/99-pisat-usb.rules`):
```
ACTION=="add", SUBSYSTEMS=="usb", SUBSYSTEM=="block", RUN+="/home/dmitry/pi-sat/scripts/usb_ingest.sh"
```

**Script Flow:**
```bash
#!/bin/bash
# usb_ingest.sh

1. Detect USB mount point
2. rsync all *.mp3 files to ~/Music/pisat/
3. Run ffmpeg-normalize (volume normalization)
4. Update MPD database (mpc update)
5. Speak: "I found X new songs" (via Piper TTS)
```

---

## Data Flow Examples

### Example 1: "Play Frozen"

```
1. Wake Word Detected
   ↓
2. MPD Volume: 100% → 10% (ducking)
   ↓
3. SpeechRecorder: Records 2 seconds of audio
   ↓
4. HailoSTT: Transcribes → "play frozen"
   ↓
5. IntentEngine: classify_command("play frozen")
   → intent='play', query='frozen'
   ↓
6. MPDController: fuzzy_search_and_play("frozen")
   → Finds "Frozen - Let It Go.mp3" (score: 92%)
   ↓
7. MPD: Starts playing
   ↓
8. TTS: "Playing Frozen Let It Go"
   ↓
9. MPD Volume: 10% → 100% (restore)
```

### Example 2: Mic Mute Button (Unmute)

```
1. User unmutes microphone (hardware button)
   ↓
2. MicMuteDetector: Audio level rises above threshold
   ↓
3. MicMuteDetector: on_unmute() callback triggered
   ↓
4. Orchestrator: Force listening mode activated (bypass wake word)
   ↓
5. SpeechRecorder: Start recording voice command
```

### Example 3: "I love this"

```
1. Wake Word + STT → "I love this"
   ↓
2. IntentEngine: intent='like'
   ↓
3. MPDController: add_to_favorites(current_song)
   → Appends filename to ~/Music/pisat/favorites.m3u
   ↓
4. TTS: "Added to favorites"
```

### Example 4: "Stop in 30 minutes"

```
1. Wake Word + STT → "stop in 30 minutes"
   ↓
2. IntentEngine: intent='sleep', params='30'
   ↓
3. MPDController: sleep_timer(30)
   → Schedules fade-out starting at 29:30
   → Stops playback at 30:00
   ↓
4. TTS: "I'll stop in 30 minutes"
```

---

## Configuration Management

### File: `config.py`

**Keep existing:**
- Audio settings (RATE, CHUNK, etc.)
- Wake word settings (THRESHOLD, MODELS)
- VAD settings (VAD_LEVEL, SILENCE_THRESHOLD)
- STT settings (HAILO_STT_MODEL)

**Remove:**
- HA_BASE_URL
- HA_TOKEN

**Add new:**
```python
# MPD Configuration
MPD_HOST = os.getenv('MPD_HOST', 'localhost')
MPD_PORT = int(os.getenv('MPD_PORT', 6600))
MUSIC_LIBRARY = os.getenv('PISAT_MUSIC_DIR', f'{os.path.expanduser("~")}/Music/pisat')

# TTS Configuration (Piper)
PIPER_MODEL_PATH = os.getenv('PIPER_MODEL', f'{PROJECT_ROOT}/resources/voices/en_US-lessac-medium.onnx')

# Mic Mute Detection Configuration
MIC_MUTE_ENABLED = os.getenv('MIC_MUTE_ENABLED', 'true').lower() == 'true'
MIC_MUTE_THRESHOLD = float(os.getenv('MIC_MUTE_THRESHOLD', 0.01))

# Fuzzy Matching
FUZZY_MATCH_THRESHOLD = 50  # Minimum score to consider a match
```

---

## Dependencies Update

### New `requirements.txt` additions:

```
# Existing dependencies (keep all)
openwakeword
pyaudio
numpy<2
soundfile
webrtcvad
scipy
librosa
transformers
torch

# NEW: Music player
python-mpd2>=3.1.0

# NEW: Fuzzy matching
thefuzz>=0.20.0
python-Levenshtein>=0.21.0  # Faster fuzzy matching
```

### System Dependencies (APT):

```bash
# MPD and client tools
sudo apt-get install mpd mpc

# Piper TTS
# (Manual download from https://github.com/rhasspy/piper/releases)
wget https://github.com/rhasspy/piper/releases/download/v1.2.0/piper_arm64.tar.gz
tar xzf piper_arm64.tar.gz
sudo cp piper/piper /usr/local/bin/

# Voice model
mkdir -p resources/voices
wget https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx

# Audio normalization (for USB ingest)
sudo apt-get install ffmpeg-normalize

# direnv
sudo apt-get install direnv
```

---

## Testing Strategy

### Existing Tests (Keep All)

All 20+ test files remain valid:
- `test_wake_word.py`
- `test_speech_recorder.py`
- `test_hailo_stt_suite.py`
- `test_orchestrator_e2e.py`
- etc.

### New Tests to Add

1. **`tests/test_intent_engine.py`**
   - Test fuzzy command matching
   - Test parameter extraction
   - Test confidence scoring

2. **`tests/test_mpd_controller.py`**
   - Test MPD connection
   - Test play/pause/skip
   - Test fuzzy search
   - Test volume ducking
   - Test favorites management

3. **`tests/test_piper_tts.py`**
   - Test TTS generation
   - Test response templates

4. **`tests/test_mic_mute_detector.py`**
   - Test audio level monitoring
   - Test mute/unmute detection
   - Test threshold sensitivity

5. **`tests/test_integration_music.py`**
   - End-to-end: Wake word → Music plays
   - Test "I love this" workflow

---

## File Structure

```
pi-sat/
├── modules/
│   ├── orchestrator.py           # MODIFY: Route to intent engine
│   ├── wake_word_listener.py     # KEEP AS-IS
│   ├── speech_recorder.py        # MODIFY: Add volume ducking
│   ├── hailo_stt.py              # KEEP AS-IS
│   ├── audio_player.py           # KEEP AS-IS (wake sound)
│   ├── audio_devices.py          # KEEP AS-IS
│   ├── logging_utils.py          # KEEP AS-IS
│   ├── home_assistant.py         # DELETE
│   ├── intent_engine.py          # NEW
│   ├── mpd_controller.py         # NEW
│   ├── piper_tts.py              # NEW
│   ├── mic_mute_detector.py      # NEW
│   └── __init__.py
├── scripts/
│   ├── usb_ingest.sh             # NEW
│   └── setup_mpd.sh              # NEW
├── resources/
│   ├── wakesound.wav             # EXISTS
│   └── voices/                   # NEW
│       └── en_US-lessac-medium.onnx
├── tests/
│   ├── [all existing tests]      # KEEP
│   ├── test_intent_engine.py     # NEW
│   ├── test_mpd_controller.py    # NEW
│   └── test_piper_tts.py         # NEW
├── config.py                     # MODIFY: Add MPD/mic mute config
├── requirements.txt              # MODIFY: Add new deps
├── .envrc                        # UPDATED
├── .envrc.local.example          # UPDATED
├── pi-sat.sh                     # MODIFY: Add MPD setup commands
├── ARCHITECTURE.md               # NEW (this file)
├── CLAUDE.md                     # UPDATE
└── README.md                     # UPDATE
```

---

## Implementation Phases

### Phase 1: Foundation (Core Music Playback)
- Remove Home Assistant integration
- Implement IntentEngine (basic command classification)
- Implement MPDController (play/pause/skip)
- Update Orchestrator to route through IntentEngine
- Add TTS responses (Piper)
- **Goal**: "Play", "Pause", "Skip" voice commands work

### Phase 2: Smart Features
- Fuzzy music search
- "I love this" favorites
- Volume control commands
- **Goal**: Natural language music search works

### Phase 3: Advanced Features
- Mic mute button detection (analog audio level monitoring)
- **Goal**: Force listening mode via mic unmute works

### Phase 4: Polish & Extras
- Volume ducking (auto-lower on wake word)
- Sleep timer with fade-out
- USB auto-ingest
- **Goal**: All features from requirements implemented

---

## Notes

- **No LLM needed**: Fuzzy matching is fast enough for kid-friendly commands
- **Hailo stays**: Wake word and STT keep Hailo acceleration
- **MPD is rock-solid**: Industry standard music daemon, low resource usage
- **Piper is best offline TTS**: Fast, human-sounding, runs on Pi 5
- **Mic mute detection**: Simple analog audio level monitoring, no GPIO needed
