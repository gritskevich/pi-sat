# Implementation Patterns

Detailed implementation patterns for Pi-Sat modules. This document provides in-depth code examples and explanations for each component.

**Quick Navigation:**
- [Wake Word Listener](#wake-word-listener)
- [Speech Recorder](#speech-recorder)
- [Hailo STT](#hailo-stt)
- [Intent Engine](#intent-engine)
- [MPD Controller](#mpd-controller)
- [Interactive Player](#interactive-player)
- [Volume Manager](#volume-manager)
- [Piper TTS](#piper-tts)
- [Mic Mute Detector](#mic-mute-detector-to-implement)
- [Orchestrator Integration](#orchestrator-integration)

---

## Wake Word Listener
**File:** `modules/wake_word_listener.py`

**Key Pattern:** Lazy PyAudio initialization
```python
class WakeWordListener:
    def __init__(self):
        self.audio = None  # Don't create PyAudio in __init__

    def start_listening(self):
        if self.audio is None:
            self.audio = pyaudio.PyAudio()  # Create only when needed
```

**Why:** Avoids lingering threads during tests

**Resampling:** 48kHz device audio → 16kHz for model
```python
def resample_audio(audio_data, orig_rate=48000, target_rate=16000):
    # Linear interpolation for speed
    ratio = target_rate / orig_rate
    new_length = int(len(audio_data) * ratio)
    return np.interp(
        np.linspace(0, len(audio_data), new_length),
        np.arange(len(audio_data)),
        audio_data
    )
```

**Cooldown:** 2-second debounce to prevent spam detections

---

## Speech Recorder
**File:** `modules/speech_recorder.py`

### Adaptive VAD Pattern (NEW - 2025-12-19)

**Key Innovation:** Dual VAD with adaptive noise floor calibration

**Pattern:** Stream-based recording with energy-based detection
```python
def record_from_stream(self, stream, input_rate=48000, max_duration=10.0):
    """
    Record from existing PyAudio stream with adaptive silence detection.

    Features:
    - Noise floor calibration (first 0.3s)
    - Dual VAD: WebRTC + Energy-based (both must agree)
    - Adaptive threshold based on environment
    - Smart end-of-speech detection
    - Zero gap (uses same stream as wake word detection)
    """
    # Phase 1: Calibration (0.3s) - Measure ambient noise
    calibration_energy = []
    for _ in range(calibration_frames):
        data = stream.read(config.CHUNK, exception_on_overflow=False)
        audio_16k = resample_to_16khz(data, input_rate)
        energy = np.sqrt(np.mean(audio_16k.astype(np.float32) ** 2))
        calibration_energy.append(energy)

    noise_floor = np.median(calibration_energy)

    # Phase 2: Recording with adaptive detection
    while True:
        data = stream.read(config.CHUNK)
        audio_16k = resample_to_16khz(data, input_rate)
        energy = calculate_rms_energy(audio_16k)

        # Dual VAD check
        is_speech_vad = vad.is_speech(audio_16k.tobytes(), 16000)  # WebRTC
        is_speech_energy = energy > (noise_floor * config.VAD_SPEECH_MULTIPLIER)

        # Both must agree for positive detection
        is_speech = is_speech_vad and is_speech_energy

        if is_speech:
            speech_frame_count += 1
            silence_frames = 0
        else:
            silence_frames += 1

        # End condition: enough silence after minimum speech
        if silence_frames >= silence_frames_threshold and \
           speech_frame_count >= min_speech_frames:
            break
```

**Why Dual VAD:**
- WebRTC VAD alone can false-trigger on consistent noise
- Energy-based alone can miss soft speech in noisy environments
- Combining both (AND logic) provides robust detection

**Adaptive Parameters (from config):**
```python
# Configurable via environment or config.py
VAD_SPEECH_MULTIPLIER = 1.3  # Speech must be 1.3x louder than noise
VAD_SILENCE_DURATION = 1.2   # Wait 1.2s of silence before ending
VAD_MIN_SPEECH_DURATION = 0.5  # Require minimum 0.5s of speech
```

**Calibration Tool:**
```bash
./pi-sat.sh calibrate_vad
```

Output provides:
- Noise floor measurement (RMS)
- Speech level measurement (RMS)
- Signal-to-Noise Ratio (SNR)
- Recommended multiplier and silence duration
- Energy distribution histogram

**Example Calibration Output:**
```
📊 Noise Floor (median): 338.3 RMS
🗣️  Speech Median: 515.1 RMS
📈 Signal-to-Noise Ratio: 1.52x

❌ Low SNR - Use multiplier: 1.3x (noisy environment)
   Speech threshold: 439.8 RMS
⏱️  Recommended silence duration: 1.2s
```

**Stream-Based Recording (Zero Gap):**
- Uses same PyAudio stream as wake word detection
- No stream stop/start overhead
- Immediate recording after wake word detection
- Eliminates ~200-500ms gap present in old implementation

**Old vs New:**
```python
# OLD: Create new stream (has gap)
def record_command(self):
    p = pyaudio.PyAudio()
    stream = p.open(...)  # ~200ms overhead
    # ... record ...
    stream.close()
    p.terminate()

# NEW: Use existing stream (zero gap)
def record_from_stream(self, stream):
    # Stream already open from wake word detection
    # Immediate recording start
    data = stream.read(...)  # No overhead
```

**Volume Management:** ✅ Unified VolumeManager module

**Key Pattern:** Separate volumes for music and TTS
```python
from modules.volume_manager import VolumeManager

# Initialize with MPD controller (optional)
volume_manager = VolumeManager(mpd_controller=mpd_controller)

# Music volume (MPD software volume or ALSA fallback)
volume_manager.set_music_volume(50)
volume_manager.duck_music_volume(duck_to=20)  # Lower music for voice input
volume_manager.restore_music_volume()  # Restore after voice input

# TTS volume (ALSA hardware volume, independent of music)
volume_manager.set_tts_volume(80)  # Normal volume for responses
```

**Volume Ducking in Orchestrator:**
```python
# In orchestrator._process_command():
duck_level = config.VOLUME_DUCK_LEVEL  # Default: 20%
self.volume_manager.duck_music_volume(duck_to=duck_level)
try:
    # ... record and process command ...
finally:
    self.volume_manager.restore_music_volume()  # Always restore
```

**Volume Control Methods:**
- **MPD Software Volume**: `client.setvol(0-100)` if enabled in MPD config
- **ALSA Hardware Volume**: `amixer set Master X%` (fallback when MPD volume disabled)
- **Automatic Detection**: VolumeManager detects available method on init

---

## Hailo STT
**File:** `modules/hailo_stt.py`

**Key Pattern:** Singleton pattern with retry logic
```python
class HailoSTT:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize_pipeline()
        return cls._instance

    def transcribe(self, audio_data):
        # Built-in retry logic for transient errors
        return self._transcribe_with_retry(audio_data)
```

**Why:** Only one Hailo pipeline instance allowed (resource constraint)

**Fallback:** CPU inference if Hailo unavailable (dev environment)

**Error Recovery:** Automatic retry with exponential backoff
- Retries on transient errors (RuntimeError, ConnectionError, OSError, IOError)
- Configurable via `STT_MAX_RETRIES`, `STT_RETRY_DELAY`, `STT_RETRY_BACKOFF`
- Logs retry attempts and success/failure
- Returns empty string after max retries exhausted

**Language Configuration:** ✅ Configurable (2025-12-15)
- Set via `config.HAILO_STT_LANGUAGE` (default: 'fr')
- Supports: 'fr', 'en', 'es', and other Whisper languages
- Language token injected at decoder initialization

**Expected Input:** 16kHz mono WAV audio

**Performance:** ~1-2 seconds inference time with Hailo-8L

---

## Intent Engine
**File:** `modules/intent_engine.py`

**Status:** ✅ Implemented with priority-based fuzzy matching

**Key Pattern:** Priority-based intent classification (intent only)
```python
from thefuzz import fuzz, process
from dataclasses import dataclass

@dataclass
class Intent:
    intent_type: str      # play_music, pause, volume_up, etc.
    confidence: float      # 0.0 - 1.0
    parameters: Dict      # Extracted params (query, duration_minutes, etc.)
    raw_text: str         # Original transcribed text

INTENT_PATTERNS = {
    'play_music': {
        'triggers': ['play', 'play song', 'put on', 'start playing'],
        'extract': None,  # Query extraction moved to MusicResolver
        'priority': 10,
    },
    'sleep_timer': {
        'triggers': ['stop in 30 minutes', 'turn off in', 'set sleep timer'],
        'extract': r'(?:stop|turn off|timer)\s+(?:in\s+)?(\d+)\s*(?:minute|min)',
        'priority': 20,  # Higher priority to match before "stop"
    },
    # ... more patterns
}

def classify(text: str) -> Optional[Intent]:
    """
    Classify voice command using priority-based fuzzy matching.

    Algorithm: token_set_ratio (handles extra words better than token_sort)
    Priority: Higher priority intents checked first (sleep_timer before stop)

    Returns: Intent object or None if no match above threshold

    Examples:
        "play frozen" → Intent('play_music', 0.95, {}, ...)
        "stop in 30 minutes" → Intent('sleep_timer', 0.9, {'duration_minutes': 30}, ...)
    """
    # Sort by priority (highest first)
    for intent_type, pattern in sorted(
        INTENT_PATTERNS.items(),
        key=lambda x: x[1]['priority'],
        reverse=True
    ):
        match_result = process.extractOne(
            text,
            pattern['triggers'],
            scorer=fuzz.token_set_ratio  # Better for extra words
        )

        if match_result and match_result[1] >= fuzzy_threshold:
            # Extract parameters using regex
            params = extract_params(text, pattern['extract'])
            return Intent(intent_type, match_result[1] / 100.0, params, text)

    return None
```

**Parameter Extraction (Regex-based):**
```python
def extract_params(text: str, regex_pattern: str) -> Dict:
    """
    Extract parameters using regex patterns.

    Examples:
        "stop in 30 minutes" → {'duration_minutes': 30}
        "stop in 15 min" → {'duration_minutes': 15}
    """
    match = re.search(regex_pattern, text, re.IGNORECASE)
    if match:
        if 'minute' in regex_pattern.lower():
            return {'duration_minutes': int(match.group(1))}
    return {}
```

**Fuzzy Music Search:**
```python
def search_music(query: str, music_library: List[str]) -> Optional[Tuple[str, float]]:
    """
    Fuzzy search with typo tolerance.

    Algorithm: token_set_ratio (handles partial matches)
    Threshold: Uses IntentEngine.fuzzy_threshold (default: 50)

    Examples:
        "frozzen" → ("Frozen - Let It Go", 0.85)
        "beatles" → ("The Beatles - Hey Jude", 0.90)
    """
    match_result = process.extractOne(
        query,
        music_library,
        scorer=fuzz.token_set_ratio
    )

    if match_result and match_result[1] >= self.fuzzy_threshold:
        return (match_result[0], match_result[1] / 100.0)
    return None
```

**Key Improvements Over Naive Approach:**
- **Priority system**: Prevents "stop in 30 minutes" matching as "stop" intent
- **token_set_ratio**: Better than token_sort_ratio for handling extra words ("could you play frozen please")
- **Structured Intent**: Dataclass with type safety vs tuple unpacking

---

## Music Resolver
**File:** `modules/music_resolver.py`

**Status:** ✅ Implemented

**Key Pattern:** Extract query from utterance, then resolve against catalog
```python
resolver = MusicResolver(music_library)
resolution = resolver.resolve("Je vais écouter. Alors, on danse.")

# resolution.query -> "alors on danse"
# resolution.matched_file -> ".../Stromae - Alors on danse - Radio Edit.mp3"
```

**Notes:**
- Keeps IntentEngine music-agnostic
- Handles fuzzy phrasing and punctuation before matching
- Uses MusicLibrary for final selection (phonetic + text hybrid)

---

## MPD Controller
**File:** `modules/mpd_controller.py`

**Status:** ✅ Implemented and tested (2025-12-14)

**Key Pattern:** Persistent connection with reconnection wrapper
```python
from mpd import MPDClient
from functools import wraps

class MPDController:
    def __init__(self, host='localhost', port=6600):
        self.host = host
        self.port = port
        self.client = None
        self.original_volume = 100
        self.connect()

    def connect(self):
        """Connect with retry logic"""
        try:
            self.client = MPDClient()
            self.client.connect(self.host, self.port)
        except Exception as e:
            logger.error(f"MPD connection failed: {e}")
            self.client = None

    def _reconnect_on_error(func):
        """Decorator: retry command once on connection error"""
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except Exception as e:
                logger.warning(f"MPD error, reconnecting: {e}")
                self.connect()
                return func(self, *args, **kwargs)
        return wrapper

    @_reconnect_on_error
    def play(self, query=None):
        if query:
            # Fuzzy search and play
            results = self.fuzzy_search(query)
            if results:
                self.client.clear()
                self.client.add(results[0])
                self.client.play()
        else:
            # Resume current
            self.client.play()

    @_reconnect_on_error
    def pause(self):
        self.client.pause(1)

    @_reconnect_on_error
    def skip(self):
        self.client.next()

    @_reconnect_on_error
    def previous(self):
        self.client.previous()

    @_reconnect_on_error
    def set_volume(self, level):
        """Set volume 0-100 (MPD software volume)"""
        self.client.setvol(max(0, min(100, level)))

    def volume_up(self, amount=10):
        """Increase volume (MPD software volume only)"""
        with self._ensure_connection():
            status = self.client.status()
            current = int(status.get('volume', 50))
            new_volume = min(100, current + amount)
            self.client.setvol(new_volume)
            return (True, f"Volume {new_volume}%")

    def volume_down(self, amount=10):
        """Decrease volume (MPD software volume only)"""
        with self._ensure_connection():
            status = self.client.status()
            current = int(status.get('volume', 50))
            new_volume = max(0, current - amount)
            self.client.setvol(new_volume)
            return (True, f"Volume {new_volume}%")

    # Note: ALSA fallback for hardware volume control is implemented
    # in scripts/player.py (get_alsa_volume, set_alsa_volume functions)

    def duck_volume(self, restore=False):
        """Lower to 10% or restore original"""
        if restore:
            self.set_volume(self.original_volume)
        else:
            status = self.client.status()
            self.original_volume = int(status.get('volume', 100))
            self.set_volume(10)

    @_reconnect_on_error
    def fuzzy_search(self, query):
        """Search library with fuzzy matching"""
        from thefuzz import process, fuzz

        # Get all songs
        all_songs = self.client.listall()

        # Extract filenames/titles
        songs = [s['file'] for s in all_songs if 'file' in s]

        # Fuzzy match
        matches = process.extractBests(
            query,
            songs,
            scorer=fuzz.token_sort_ratio,
            score_cutoff=75,
            limit=5
        )

        return [m[0] for m in matches]

    @_reconnect_on_error
    def add_to_favorites(self):
        """Add current song to favorites.m3u"""
        current = self.client.currentsong()
        if 'file' in current:
            self.client.playlistadd('favorites', current['file'])

    @_reconnect_on_error
    def play_favorites(self):
        """Play favorites playlist"""
        self.client.clear()
        self.client.load('favorites')
        self.client.play()

    def sleep_timer(self, minutes):
        """Schedule stop with 30s fade-out"""
        import threading

        def fade_and_stop():
            time.sleep(minutes * 60 - 30)  # Wait until 30s before end

            # Fade out over 30 seconds
            for vol in range(100, 0, -5):
                self.set_volume(vol)
                time.sleep(1.5)  # 20 steps × 1.5s = 30s

            self.pause()

        thread = threading.Thread(target=fade_and_stop, daemon=True)
        thread.start()
```

**Playlist Support:**
- Favorites playlist: `~/.mpd/playlists/favorites.m3u`
- Local playlists: Can load from `pi-sat/playlist/` folder
- Test utility: `scripts/test_playlist.py`

**Volume Control:**
- MPD software volume: `client.setvol(0-100)` if enabled
- ALSA hardware volume: `amixer set Master` (fallback)
- Volume ducking: Lower to 10% during voice input
- Debug utility: `scripts/test_volume.py`

---

## Interactive Player
**File:** `scripts/player.py`

**Status:** ✅ Implemented (2025-12-14)

**Purpose:** Interactive command-line MPD player with keyboard controls

**Key Features:**
- Real-time status display (song, artist, time, volume, shuffle)
- Volume control with ALSA fallback
- Arrow key navigation (termios raw mode)
- Graceful exit handling (Ctrl-C, ESC)

**Controls:**
- `↑/↓` - Volume up/down (5% steps)
- `←/→` - Previous/Next song
- `S` - Toggle shuffle
- `Space` - Play/Pause
- `ESC` - Exit

**Volume Control Pattern:**
```python
# ALSA volume helpers (when MPD software volume disabled)
def get_alsa_volume():
    """Get ALSA Master volume via amixer"""
    result = subprocess.run(['amixer', 'get', 'Master'],
                           capture_output=True, text=True, timeout=1)
    # Parse: "Front Left: Playback 26304 [40%] [on]"
    for line in result.stdout.split('\n'):
        if '[' in line and '%' in line:
            start = line.find('[') + 1
            end = line.find('%', start)
            return int(line[start:end]) if start > 0 else None
    return None

def set_alsa_volume(percent):
    """Set ALSA Master volume via amixer"""
    subprocess.run(['amixer', 'set', 'Master', f'{percent}%'],
                  capture_output=True, timeout=1)

# Volume control with fallback
def volume_up(controller, amount=5):
    """Try MPD volume first, fallback to ALSA"""
    try:
        with controller._ensure_connection():
            status = controller.client.status()
            volume_str = status.get('volume')
            if volume_str and volume_str not in ('n/a', '-1', None):
                # MPD software volume available
                controller.volume_up(amount)
                return
    except:
        pass

    # Fallback to ALSA hardware volume
    current = get_alsa_volume()
    if current is not None:
        set_alsa_volume(min(100, current + amount))
```

**Arrow Key Detection:**
- Uses `fcntl` for non-blocking reads
- Captures full escape sequence (`\x1b[C` for RIGHT)
- Ignores incomplete sequences (prevents accidental ESC)
- Raw terminal mode with proper cleanup

**Status Display:**
```
▶ [ 40%] 🔀 Song Name - Artist Name [00:15/03:28]
```

---

## Volume Manager
**File:** `modules/volume_manager.py`

**Status:** ✅ Implemented (2025-12-14)

**Purpose:** Unified volume control for music playback and TTS with separate volume management

**Key Features:**
- **Separate Volumes**: Music volume (MPD/ALSA) and TTS volume (ALSA) managed independently
- **Automatic Detection**: Detects MPD software volume availability, falls back to ALSA
- **Volume Ducking**: Lowers music volume during voice input, preserves TTS volume
- **Volume Restoration**: Automatically restores original music volume after voice input

**Usage Pattern:**
```python
from modules.volume_manager import VolumeManager
from modules.mpd_controller import MPDController

# Initialize
mpd_controller = MPDController()
volume_manager = VolumeManager(mpd_controller=mpd_controller)

# Music volume control
volume_manager.set_music_volume(50)  # Set to 50%
volume_manager.music_volume_up(10)   # Increase by 10%
volume_manager.music_volume_down(10) # Decrease by 10%

# TTS volume control (independent)
volume_manager.set_tts_volume(80)    # Set TTS to 80%

# Volume ducking for voice input
volume_manager.duck_music_volume(duck_to=20)  # Lower music to 20%
# ... record voice command ...
volume_manager.restore_music_volume()  # Restore original
```

**Volume Control Methods:**
1. **MPD Software Volume** (preferred): `client.setvol(0-100)` if enabled in MPD config
2. **ALSA Hardware Volume** (fallback): `amixer set Master X%` when MPD volume disabled

**Integration with Orchestrator:**
- Orchestrator automatically ducks music volume before recording
- Volume is restored after command processing (even on errors)
- TTS volume remains at configured level (config.TTS_VOLUME)

**Configuration:**
```python
# config.py
VOLUME_DUCK_LEVEL = 20  # Duck music to 20% during voice input
TTS_VOLUME = 80         # TTS volume (0-100)
VOLUME_STEP = 10        # Volume change step for up/down commands
```

---

## Piper TTS
**File:** `modules/piper_tts.py`

**Status:** ✅ Implemented and verified (2025-12-14)

**Key Features:**
- Audio device validation on initialization
- Volume management via VolumeManager
- Error handling with graceful fallback
- Response templates for common intents

**Volume Control:**
- Accepts optional `volume_manager` parameter in constructor
- Uses `config.TTS_VOLUME` (default: 80) when volume_manager available
- Temporarily sets TTS volume during playback, restores original after
- Volume is independent of music volume

**Audio Device Configuration:**
- Uses `config.PIPER_OUTPUT_DEVICE` (default: 'default')
- Validates device availability on initialization
- Supports ALSA device names: 'default', 'plughw:0,0', 'hw:0,0'

**Response Templates:**
- `'playing'`: "Playing {song}"
- `'paused'`: "Paused"
- `'skipped'`: "Skipping"
- `'volume_up'`: "Volume up"
- `'volume_down'`: "Volume down"
- `'liked'`: "Added to favorites"
- `'no_match'`: "I don't know that song"
- `'error'`: "Sorry, something went wrong"
- `'unknown'`: "I didn't understand that"
- `'sleep_timer'`: "I'll stop in {minutes} minutes"

**Performance:** Real-time factor 0.3 (generates speech 3× faster than playback)

---

## Mic Mute Detector (To Implement)
**File:** `modules/mic_mute_detector.py`

**Key Pattern:** Audio level monitoring (no GPIO)
```python
import pyaudio
import numpy as np
import threading

class MicMuteDetector:
    def __init__(self, threshold=0.01, callback=None):
        self.threshold = threshold
        self.callback = callback
        self.is_muted = False
        self.monitoring = False
        self.thread = None

    def start_monitoring(self):
        """Start audio level monitoring thread"""
        self.monitoring = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()

    def _monitor_loop(self):
        """Main monitoring loop"""
        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=1024
        )

        while self.monitoring:
            try:
                data = stream.read(1024, exception_on_overflow=False)
                audio_data = np.frombuffer(data, dtype=np.int16)

                # Calculate RMS level
                rms = np.sqrt(np.mean(audio_data**2))
                normalized_level = rms / 32768.0  # Normalize to 0-1

                # Detect state change
                currently_muted = normalized_level < self.threshold

                if self.is_muted and not currently_muted:
                    # Unmute detected
                    logger.info("Mic unmuted - triggering force listening")
                    if self.callback:
                        self.callback()

                self.is_muted = currently_muted
                time.sleep(0.1)  # Check every 100ms

            except Exception as e:
                logger.error(f"Mic monitoring error: {e}")
                time.sleep(1)

        stream.close()
        audio.terminate()
```

---

## Orchestrator Integration
**File:** `modules/orchestrator.py`

**Status:** ✅ Implemented - Main pipeline coordinator with error recovery

**Pipeline Flow:**
```python
def _on_wake_word_detected(self):
    """Called when wake word detected"""
    if self.is_processing:
        return  # Prevent concurrent processing

    self.is_processing = True
    audio_player.play_wake_sound()  # Audio feedback

    try:
        self._process_command()
    finally:
        self.is_processing = False

def _process_command(self):
    # 1. Duck music volume for better voice input
    duck_level = config.VOLUME_DUCK_LEVEL
    self.volume_manager.duck_music_volume(duck_to=duck_level)

    try:
        # 2. Record command with VAD
        audio_data = self.speech_recorder.record_command()

        # 3. Transcribe with Hailo STT (has built-in retry logic)
        text = self.stt.transcribe(audio_data)

        if text.strip():
            # 4. Classify intent
            intent = self.intent_engine.classify(text)

            if intent:
                # 5. Execute intent (MPD control)
                response = self._execute_intent(intent)

                # 6. Speak response with TTS
                if response:
                    self.tts.speak(response)
            else:
                # No intent matched
                error_msg = self.tts.get_response_template('unknown')
                self.tts.speak(error_msg)
        else:
            # No text transcribed - notify user
            error_msg = self.tts.get_response_template('error')
            self.tts.speak(error_msg)
    finally:
        # Always restore music volume (even on errors)
        self.volume_manager.restore_music_volume()
```

**Error Recovery:**
- **STT failures**: Automatic retry with exponential backoff
- **Empty transcription**: User notified via TTS error message
- **Intent classification errors**: Logged, returns None gracefully
- **Intent execution errors**: Returns error response, user notified via TTS
- **Volume restoration**: Always restored in finally block (even on errors)
- **No silent failures**: All errors logged and user notified

---

**See also:**
- [TESTING.md](./TESTING.md) - Testing strategies and patterns
- [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) - Common issues and solutions
- [RESEARCH.md](./RESEARCH.md) - Research notes and technical decisions
