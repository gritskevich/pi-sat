import os

# Project root directory (used for resource paths)
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# elevenlabs
ELEVENLABS_API_KEY = "sk_5d91289913144262de023ad7c7a4af08ff625bf49c86ea9f"

# Audio settings
CHUNK = 320
FORMAT = 'paInt16'
CHANNELS = 1
RATE = 48000
SAMPLE_RATE = 16000
INPUT_DEVICE_NAME = None  # use system default input device
OUTPUT_ALSA_DEVICE = os.getenv('OUTPUT_ALSA_DEVICE', os.getenv('PIPER_OUTPUT_DEVICE', 'default'))  # ALSA device for beep/audio_player (aplay -D)
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
THRESHOLD = 0.5  # Detection threshold (0-1). Lower = more sensitive, higher = fewer false positives
LOW_CONFIDENCE_THRESHOLD = 0.1  # Debug threshold for logging low-confidence detections
WAKE_WORD_COOLDOWN = float(os.getenv('WAKE_WORD_COOLDOWN', '3.0'))  # Seconds to ignore new activations after one fires

# OpenWakeWord optimizations (reduce false positives)
VAD_THRESHOLD = float(os.getenv('VAD_THRESHOLD', '0.6'))  # Voice Activity Detection threshold (0-1)
                                                            # Requires speech detected by Silero VAD to trigger
                                                            # 0.6 = good balance, 0.7+ = very strict
ENABLE_SPEEX_NOISE_SUPPRESSION = os.getenv('ENABLE_SPEEX', 'false').lower() == 'true'  # Noise suppression (Linux only)

# VAD settings
VAD_LEVEL = 2
FRAME_DURATION = 30
SILENCE_THRESHOLD = 1.0  # seconds of silence to mark command end
MAX_RECORDING_TIME = 10.0  # maximum seconds to record (cut off at 10s)

# Adaptive VAD settings (energy-based detection)
# Tune these based on your environment (use ./pi-sat.sh calibrate_vad)
VAD_SPEECH_MULTIPLIER = float(os.getenv('VAD_SPEECH_MULTIPLIER', '1.3'))  # Speech energy multiplier vs noise floor (1.3 = noisy, 2.0 = quiet)
VAD_SILENCE_DURATION = float(os.getenv('VAD_SILENCE_DURATION', '1.2'))  # Seconds of silence to end recording (0.8-1.5s recommended)
VAD_MIN_SPEECH_DURATION = float(os.getenv('VAD_MIN_SPEECH_DURATION', '0.5'))  # Minimum speech duration in seconds

# Hailo STT settings
HAILO_STT_MODEL = "whisper-base"  # whisper-tiny, whisper-base
HAILO_STT_LANGUAGE = os.getenv('HAILO_STT_LANGUAGE', 'fr')  # Default: French. Change to 'en' for English
HAILO_STT_DEBUG = False

# Error Recovery / Retry settings
STT_MAX_RETRIES = int(os.getenv('STT_MAX_RETRIES', '3'))  # Maximum retry attempts for STT
STT_RETRY_DELAY = float(os.getenv('STT_RETRY_DELAY', '0.5'))  # Initial retry delay in seconds
STT_RETRY_BACKOFF = float(os.getenv('STT_RETRY_BACKOFF', '2.0'))  # Exponential backoff factor

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
PIPER_OUTPUT_DEVICE = os.getenv('PIPER_OUTPUT_DEVICE', 'default')  # ALSA device for TTS playback

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

# Volume Control settings
VOLUME_STEP = int(os.getenv('VOLUME_STEP', '10'))  # Percentage (0-100) for volume up/down commands
VOLUME_DUCK_LEVEL = int(os.getenv('VOLUME_DUCK_LEVEL', '5'))  # Duck music to X% while listening for voice (0% = mute)
VOLUME_FADE_DURATION = float(os.getenv('VOLUME_FADE_DURATION', '30.0'))  # seconds for sleep timer fade
TTS_VOLUME = int(os.getenv('TTS_VOLUME', '80'))  # TTS volume (0-100) - separate from music volume
BEEP_VOLUME = int(os.getenv('BEEP_VOLUME', '40'))  # Wake sound volume (0-100) - independent of music/TTS

# Kid Safety & Parental Control settings
MAX_VOLUME = int(os.getenv('MAX_VOLUME', '80'))  # Maximum allowed volume (0-100) for kid safety
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
