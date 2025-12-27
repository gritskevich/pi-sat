import os

# Project root directory (used for resource paths)
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# ElevenLabs TTS (only used for test generation scripts, NOT runtime)
# SECURITY: Never commit API keys to source control
# Set via environment: export ELEVENLABS_API_KEY='your_key_here'
ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY', None)

# Audio settings
CHUNK = 320
FORMAT = 'paInt16'
CHANNELS = 1
RATE = 48000
SAMPLE_RATE = 16000
DEBUG_DUMMY_AUDIO = os.getenv('DEBUG_DUMMY_AUDIO', 'false').lower() == 'true'  # Use synthetic audio in debug if explicitly enabled
INPUT_DEVICE_NAME = None  # use system default input device
OUTPUT_ALSA_DEVICE = os.getenv('OUTPUT_ALSA_DEVICE', os.getenv('PIPER_OUTPUT_DEVICE', 'pulse'))  # ALSA device for beep/audio_player (aplay -D)
PLAY_WAKE_SOUND = True
# Wake sound options:
#   beep-short.wav = Short beep (100ms) - use with WAKE_SOUND_SKIP=0.0 (DEFAULT)
#   beep-instant.wav = Ultra-short beep (50ms) - use with WAKE_SOUND_SKIP=0.0 (fastest)
#   archive/wakesound.wav = Original sound (638ms) - use with WAKE_SOUND_SKIP=0.7 (legacy)
WAKE_SOUND_PATH = os.getenv('WAKE_SOUND_PATH', f'{PROJECT_ROOT}/resources/beep-short.wav')
WAKE_SOUND_SKIP_SECONDS = float(os.getenv('WAKE_SOUND_SKIP', '0.0'))  # Seconds to skip after wake sound
                                                                        # 0.0 = instant recording (beep plays while recording)
                                                                        # 0.1 = skip short beep (cleaner audio)
                                                                        # 0.7 = skip original wake sound (cleanest)

# Wake word settings
WAKE_WORD_MODELS = ['alexa_v0.1']
INFERENCE_FRAMEWORK = 'tflite'  # tflite (faster on Linux) or onnx (broader compatibility)
THRESHOLD = float(os.getenv('WAKE_WORD_THRESHOLD', '0.20'))  # Detection threshold (0-1). Lower = more sensitive, higher = fewer false positives
                                                               # 0.50 = good balance, rejects TTS echoes (0.3-0.4)
LOW_CONFIDENCE_THRESHOLD = 0.1  # Debug threshold for logging low-confidence detections
WAKE_WORD_COOLDOWN = float(os.getenv('WAKE_WORD_COOLDOWN', '0.5'))  # Seconds to ignore new activations after one fires
TTS_COOLDOWN_SECONDS = float(os.getenv('TTS_COOLDOWN_SECONDS', '1.5'))  # Seconds to wait after TTS before enabling wake word (prevents self-triggering)

# Wake word model reset settings (prevents state carry-over between detections)
WAKE_WORD_MODEL_RESET_SILENCE_CHUNKS = int(os.getenv('WAKE_WORD_RESET_CHUNKS', '25'))  # Silence chunks to feed for reset
WAKE_WORD_MODEL_RESET_ITERATIONS = int(os.getenv('WAKE_WORD_RESET_ITERATIONS', '5'))   # Reset iteration count

# OpenWakeWord optimizations (reduce false positives, handle background noise/music)
VAD_THRESHOLD = float(os.getenv('VAD_THRESHOLD', '0.6'))  # Voice Activity Detection threshold (0-1)
                                                            # Requires speech detected by Silero VAD to trigger
                                                            # 0.6 = good balance, 0.7+ = very strict
ENABLE_SPEEX_NOISE_SUPPRESSION = os.getenv('ENABLE_SPEEX', 'true').lower() == 'true'  # SpeexDSP noise reduction (recommended for music/noise)

# VAD settings
VAD_LEVEL = 2
FRAME_DURATION = 30
SILENCE_THRESHOLD = 1.0  # seconds of silence to mark command end
MAX_RECORDING_TIME = 10.0  # maximum seconds to record (cut off at 10s)

# Adaptive VAD settings (energy-based detection)
# Tune these based on your environment (use ./pi-sat.sh calibrate_vad)
VAD_SPEECH_MULTIPLIER = float(os.getenv('VAD_SPEECH_MULTIPLIER', '1.25'))  # Speech energy multiplier vs noise floor (1.25 = sensitive/low mic, 1.5 = balanced, 2.0 = quiet room)
VAD_SILENCE_DURATION = float(os.getenv('VAD_SILENCE_DURATION', '1.0'))  # Seconds of silence to end recording (0.8-1.5s recommended)
VAD_MIN_SPEECH_DURATION = float(os.getenv('VAD_MIN_SPEECH_DURATION', '0.5'))  # Minimum speech duration in seconds
VAD_CONSECUTIVE_SILENCE_FRAMES = int(os.getenv('VAD_CONSECUTIVE_SILENCE_FRAMES', '30'))  # Consecutive silent frames to end (30 frames @ 30ms = 0.9s)

# Audio Normalization (command recording only, NOT wake word detection)
# Normalizes volume for close vs far speech - improves STT accuracy
AUDIO_NORMALIZATION_ENABLED = os.getenv('AUDIO_NORMALIZATION_ENABLED', 'true').lower() == 'true'
AUDIO_TARGET_RMS = float(os.getenv('AUDIO_TARGET_RMS', '3000.0'))  # Target level (3000 = optimal for Whisper STT)

# Hailo STT settings
HAILO_STT_MODEL = "whisper-base"  # whisper-tiny, whisper-base
HAILO_STT_LANGUAGE = os.getenv('HAILO_STT_LANGUAGE', 'fr')  # Default: French. Change to 'en' for English
HAILO_STT_DEBUG = False

# Error Recovery / Retry settings
STT_MAX_RETRIES = int(os.getenv('STT_MAX_RETRIES', '3'))  # Maximum retry attempts for STT
STT_RETRY_DELAY = float(os.getenv('STT_RETRY_DELAY', '0.5'))  # Initial retry delay in seconds
STT_RETRY_BACKOFF = float(os.getenv('STT_RETRY_BACKOFF', '2.0'))  # Exponential backoff factor
STT_LOCK_TIMEOUT = float(os.getenv('STT_LOCK_TIMEOUT', '15.0'))  # Lock acquisition timeout (seconds)
STT_REBUILD_THRESHOLD = int(os.getenv('STT_REBUILD_THRESHOLD', '2'))  # Consecutive failures before pipeline rebuild

# MPD (Music Player Daemon) settings
MPD_HOST = os.getenv('MPD_HOST', 'localhost')
MPD_PORT = int(os.getenv('MPD_PORT', '6600'))
MUSIC_LIBRARY = os.getenv('PISAT_MUSIC_DIR', os.path.expanduser('~/Music'))

# Piper TTS settings
PIPER_MODEL_PATH = os.getenv('PIPER_MODEL',
                              f'{PROJECT_ROOT}/resources/voices/fr_FR-siwis-medium.onnx')
# Optional: language-specific Piper models for scripts/tests
PIPER_MODEL_PATH_FR = os.getenv('PIPER_MODEL_FR', f'{PROJECT_ROOT}/resources/voices/fr_FR-siwis-medium.onnx')
PIPER_MODEL_PATH_EN = os.getenv('PIPER_MODEL_EN', f'{PROJECT_ROOT}/resources/voices/en_US-lessac-medium.onnx')
PIPER_BINARY_PATH = os.getenv('PIPER_BINARY', '/usr/local/bin/piper')
PIPER_OUTPUT_DEVICE = os.getenv('PIPER_OUTPUT_DEVICE', 'pulse')  # ALSA device for TTS playback

# LED Visual Feedback settings (NeoPixel/WS2812B)
LED_ENABLED = os.getenv('LED_ENABLED', 'false').lower() == 'true'
LED_GPIO_PIN = int(os.getenv('LED_GPIO_PIN', '18'))
LED_COUNT = int(os.getenv('LED_COUNT', '12'))
LED_BRIGHTNESS = int(os.getenv('LED_BRIGHTNESS', '128'))  # 0-255

# Physical Button settings
BUTTON_ENABLED = os.getenv('BUTTON_ENABLED', 'true').lower() == 'true'
BUTTON_GPIO_PIN = int(os.getenv('BUTTON_GPIO_PIN', '17'))
BUTTON_BOUNCE_TIME = int(os.getenv('BUTTON_BOUNCE_TIME', '200'))  # milliseconds
BUTTON_LONG_PRESS_DURATION = float(os.getenv('BUTTON_LONG_PRESS_DURATION', '2.0'))  # seconds

# Intent Engine settings
FUZZY_MATCH_THRESHOLD = int(os.getenv('FUZZY_MATCH_THRESHOLD', '35'))  # 0-100 (lowered for phonetic matching)
FUZZY_USE_LEVENSHTEIN = os.getenv('FUZZY_USE_LEVENSHTEIN', 'true').lower() == 'true'
PHONETIC_WEIGHT = float(os.getenv('PHONETIC_WEIGHT', '0.6'))  # Weight for phonetic vs text matching (0.0-1.0)

# ============================================================================
# VOLUME CONTROL - Single Master Volume Architecture
# ============================================================================
# Raspberry Pi 5 + PipeWire: Single volume control via PulseAudio sink (pactl)
# - MPD software volume: Fixed at 100% (set once at startup, never changed)
# - PulseAudio sink: THE ONLY runtime volume control (via VolumeManager)
# - ALSA PCM hardware: Left untouched (amixer confuses PipeWire)
#
# All audio (music, TTS, wake beep) shares the same master volume.
# Volume commands (up/down) control the PulseAudio sink only.
# ============================================================================

MASTER_VOLUME = int(os.getenv('MASTER_VOLUME', '15'))  # Startup volume (0-100)
VOLUME_STEP = int(os.getenv('VOLUME_STEP', '5'))  # Step for up/down commands (0-100)
MAX_VOLUME = int(os.getenv('MAX_VOLUME', '50'))  # Kid safety limit (0-100)
VOLUME_FADE_DURATION = float(os.getenv('VOLUME_FADE_DURATION', '30.0'))  # Sleep timer fade (seconds)

# Bedtime & Parental Controls
BEDTIME_ENABLED = os.getenv('BEDTIME_ENABLED', 'true').lower() == 'true'
BEDTIME_START = os.getenv('BEDTIME_START', '20:00')  # Quiet time start (24h format: HH:MM) - default 8pm
BEDTIME_END = os.getenv('BEDTIME_END', '08:00')  # Quiet time end (24h format: HH:MM) - default 8am
BEDTIME_WARNING_MINUTES = int(os.getenv('BEDTIME_WARNING_MINUTES', '10'))  # Warn X minutes before bedtime

# Activity Time Limits
DAILY_TIME_LIMIT_ENABLED = os.getenv('DAILY_TIME_LIMIT_ENABLED', 'true').lower() == 'true'  # Enabled by default
DAILY_TIME_LIMIT_MINUTES = int(os.getenv('DAILY_TIME_LIMIT_MINUTES', '60'))  # Max 1 hour per day (default)
TIME_LIMIT_WARNING_MINUTES = int(os.getenv('TIME_LIMIT_WARNING_MINUTES', '10'))  # Warn when X minutes left

# Morning Alarm settings
ALARM_ENABLED = os.getenv('ALARM_ENABLED', 'true').lower() == 'true'
ALARM_GENTLE_WAKEUP_DURATION = int(os.getenv('ALARM_GENTLE_WAKEUP_DURATION', '300'))  # 5 minutes gradual volume increase
ALARM_START_VOLUME = int(os.getenv('ALARM_START_VOLUME', '10'))  # Start gentle wake-up at 10%
ALARM_END_VOLUME = int(os.getenv('ALARM_END_VOLUME', '50'))  # End gentle wake-up at 50%

# Playback Mode defaults
# Continuous shuffle by default: repeat playlist + random mode.
# Override in your environment if you want different behavior.
DEFAULT_REPEAT_MODE = os.getenv('DEFAULT_REPEAT_MODE', 'playlist')  # off, single, playlist
DEFAULT_SHUFFLE_MODE = os.getenv('DEFAULT_SHUFFLE_MODE', 'true').lower() == 'true'
