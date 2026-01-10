import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# Audio
CHUNK = 320
FORMAT = 'paInt16'
CHANNELS = 1
RATE = 48000
SAMPLE_RATE = 16000
DEBUG_DUMMY_AUDIO = os.getenv('DEBUG_DUMMY_AUDIO', 'false').lower() == 'true'
INPUT_DEVICE_NAME = os.getenv('INPUT_DEVICE_NAME', 'pipewire')
OUTPUT_ALSA_DEVICE = os.getenv('OUTPUT_ALSA_DEVICE', os.getenv('PIPER_OUTPUT_DEVICE', 'default'))
PLAY_WAKE_SOUND = True
WAKE_SOUND_PATH = os.getenv('WAKE_SOUND_PATH', f'{PROJECT_ROOT}/resources/beep-short.wav')
WAKE_SOUND_SKIP_SECONDS = float(os.getenv('WAKE_SOUND_SKIP', '0.0'))

# Wake word
WAKE_WORD_MODELS = ['alexa_v0.1']
_py_version = f"{sys.version_info.major}.{sys.version_info.minor}"
INFERENCE_FRAMEWORK = 'onnx'
WAKE_WORD_FRAME_SIZE = 1280  # 80ms @ 16kHz (recommended by openwakeword)
THRESHOLD = float(os.getenv('WAKE_WORD_THRESHOLD', '0.01'))
LOW_CONFIDENCE_THRESHOLD = 0.1
WAKE_WORD_COOLDOWN = float(os.getenv('WAKE_WORD_COOLDOWN', '0.5'))
WAKE_WORD_MODEL_RESET_SILENCE_CHUNKS = int(os.getenv('WAKE_WORD_RESET_CHUNKS', '25'))
WAKE_WORD_MODEL_RESET_ITERATIONS = int(os.getenv('WAKE_WORD_RESET_ITERATIONS', '5'))
VAD_THRESHOLD = float(os.getenv('VAD_THRESHOLD', '0.6'))
# Speex noise suppression (not available for Python 3.13)
ENABLE_SPEEX_NOISE_SUPPRESSION = (
    os.getenv('ENABLE_SPEEX', 'true').lower() == 'true' and _py_version != "3.13"
)

# Recording
VAD_LEVEL = 2
FRAME_DURATION = 30
SILENCE_THRESHOLD = 1.0
MAX_RECORDING_TIME = 10.0

# Normalization
AUDIO_NORMALIZATION_ENABLED = os.getenv('AUDIO_NORMALIZATION_ENABLED', 'true').lower() == 'true'
AUDIO_TARGET_RMS = float(os.getenv('AUDIO_TARGET_RMS', '3000.0'))

# Hailo STT
HAILO_STT_MODEL = "whisper-tiny"

def _normalize_language(value: str) -> str:
    if not value:
        return "fr"
    lower = value.strip().lower()
    if lower.startswith("fr"):
        return "fr"
    if lower.startswith("en"):
        return "en"
    return lower

LANGUAGE = _normalize_language(os.getenv('LANGUAGE', 'fr'))
STT_MAX_RETRIES = int(os.getenv('STT_MAX_RETRIES', '3'))
STT_RETRY_DELAY = float(os.getenv('STT_RETRY_DELAY', '0.5'))
STT_RETRY_BACKOFF = float(os.getenv('STT_RETRY_BACKOFF', '2.0'))
STT_LOCK_TIMEOUT = float(os.getenv('STT_LOCK_TIMEOUT', '15.0'))
STT_REBUILD_THRESHOLD = int(os.getenv('STT_REBUILD_THRESHOLD', '2'))

# STT Backend
STT_BACKEND = os.getenv('STT_BACKEND', 'hailo').lower()
CPU_STT_MODEL = os.getenv('CPU_STT_MODEL', 'base')
CPU_STT_LANGUAGE = os.getenv('CPU_STT_LANGUAGE', LANGUAGE)

# Response Library
RESPONSE_LIBRARY_PATH = os.getenv('RESPONSE_LIBRARY_PATH', f'{PROJECT_ROOT}/resources/response_library.json')
INTERACTION_LOG_PATH = os.getenv('INTERACTION_LOG_PATH', f'{PROJECT_ROOT}/logs/intent_log.jsonl')
INTERACTION_LOGGER = os.getenv('INTERACTION_LOGGER', 'jsonl')

# Logging outputs: comma-separated (stdout, stderr, file)
LOG_OUTPUTS = os.getenv('LOG_OUTPUTS', 'stdout')
LOG_FILE_PATH = os.getenv('LOG_FILE_PATH', f'{PROJECT_ROOT}/logs/pisat.log')

# MPD
MPD_HOST = os.getenv('MPD_HOST', 'localhost')
MPD_PORT = int(os.getenv('MPD_PORT', '6600'))
MUSIC_LIBRARY = os.getenv('PISAT_MUSIC_DIR', os.path.expanduser('~/Music'))

# Piper TTS
PIPER_MODEL_PATH = os.getenv('PIPER_MODEL', f'{PROJECT_ROOT}/resources/voices/fr_FR-siwis-medium.onnx')
PIPER_BINARY_PATH = os.getenv('PIPER_BINARY', '/usr/local/bin/piper')
PIPER_OUTPUT_DEVICE = os.getenv('PIPER_OUTPUT_DEVICE', 'default')

# Intent matching & Music search
FUZZY_MATCH_THRESHOLD = int(os.getenv('FUZZY_MATCH_THRESHOLD', '60'))  # Raised to 60 to prevent false positives
PHONETIC_WEIGHT = float(os.getenv('PHONETIC_WEIGHT', '0.6'))
INTENT_MATCHERS = os.getenv('INTENT_MATCHERS', 'text,phonetic')

# Volume
MASTER_VOLUME = int(os.getenv('MASTER_VOLUME', '15'))
VOLUME_STEP = int(os.getenv('VOLUME_STEP', '5'))
MAX_VOLUME = int(os.getenv('MAX_VOLUME', '50'))

# Playback defaults
DEFAULT_REPEAT_MODE = os.getenv('DEFAULT_REPEAT_MODE', 'playlist')
DEFAULT_SHUFFLE_MODE = os.getenv('DEFAULT_SHUFFLE_MODE', 'true').lower() == 'true'

# Sleep Timer
SLEEP_TIMER_FADE_DURATION = int(os.getenv('SLEEP_TIMER_FADE_DURATION', '30'))  # seconds

# Time Scheduler (Bedtime enforcement)
BEDTIME_ENABLED = os.getenv('BEDTIME_ENABLED', 'false').lower() == 'true'
BEDTIME_START = os.getenv('BEDTIME_START', '21:00')  # HH:MM format
BEDTIME_END = os.getenv('BEDTIME_END', '07:00')  # HH:MM format
BEDTIME_WARNING_MINUTES = int(os.getenv('BEDTIME_WARNING_MINUTES', '15'))

# Activity Tracker (Daily time limits)
DAILY_TIME_LIMIT_ENABLED = os.getenv('DAILY_TIME_LIMIT_ENABLED', 'false').lower() == 'true'
DAILY_TIME_LIMIT_MINUTES = int(os.getenv('DAILY_TIME_LIMIT_MINUTES', '120'))  # 2 hours default
TIME_LIMIT_WARNING_MINUTES = int(os.getenv('TIME_LIMIT_WARNING_MINUTES', '15'))
ACTIVITY_TRACKER_STORAGE = os.getenv('ACTIVITY_TRACKER_STORAGE', os.path.expanduser('~/.pisat_usage.json'))

# Morning Alarm
ALARM_ENABLED = os.getenv('ALARM_ENABLED', 'false').lower() == 'true'
ALARM_FADE_DURATION = int(os.getenv('ALARM_FADE_DURATION', '300'))  # 5 minutes
ALARM_START_VOLUME = int(os.getenv('ALARM_START_VOLUME', '10'))  # 10%
ALARM_END_VOLUME = int(os.getenv('ALARM_END_VOLUME', '50'))  # 50%

# USB Button Controller (Physical button on speaker)
USB_BUTTON_ENABLED = os.getenv('USB_BUTTON_ENABLED', 'false').lower() == 'true'
USB_BUTTON_DEVICE_PATH = os.getenv('USB_BUTTON_DEVICE_PATH', None)  # Auto-detect if None
USB_BUTTON_DEVICE_FILTER = os.getenv('USB_BUTTON_DEVICE_FILTER', 'USB Audio')
USB_BUTTON_DOUBLE_PRESS_WINDOW = float(os.getenv('USB_BUTTON_DOUBLE_PRESS_WINDOW', '0.4'))  # 400ms
USB_BUTTON_LONG_PRESS_THRESHOLD = float(os.getenv('USB_BUTTON_LONG_PRESS_THRESHOLD', '0.8'))  # 800ms
USB_BUTTON_DEBUG = os.getenv('USB_BUTTON_DEBUG', 'false').lower() == 'true'
