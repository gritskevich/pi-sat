import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

def _env_str(key: str, default: str) -> str:
    return os.getenv(key, default)

def _env_int(key: str, default: int) -> int:
    return int(os.getenv(key, str(default)))

def _env_float(key: str, default: float) -> float:
    return float(os.getenv(key, str(default)))

def _env_bool(key: str, default: bool) -> bool:
    default_str = "true" if default else "false"
    return os.getenv(key, default_str).lower() == "true"

# Audio
CHUNK = 320
FORMAT = 'paInt16'
CHANNELS = 1
RATE = 48000
SAMPLE_RATE = 16000
DEBUG_DUMMY_AUDIO = _env_bool('DEBUG_DUMMY_AUDIO', False)
INPUT_DEVICE_NAME = _env_str('INPUT_DEVICE_NAME', 'USB Microphone')
OUTPUT_ALSA_DEVICE = _env_str('OUTPUT_ALSA_DEVICE', _env_str('PIPER_OUTPUT_DEVICE', 'default'))
PLAY_WAKE_SOUND = True
WAKE_SOUND_PATH = _env_str('WAKE_SOUND_PATH', f'{PROJECT_ROOT}/resources/beep-short.wav')
WAKE_SOUND_SKIP_SECONDS = _env_float('WAKE_SOUND_SKIP', 0.0)

# Wake word
WAKE_WORD_MODELS = [f'{PROJECT_ROOT}/resources/wakewords/coucou_eris.onnx']
INFERENCE_FRAMEWORK = 'onnx'
WAKE_WORD_THRESHOLD = _env_float('WAKE_WORD_THRESHOLD', 0.14)
WAKE_WORD_MIN_CONSECUTIVE = _env_int('WAKE_WORD_MIN_CONSECUTIVE', 3)
WAKE_WORD_COOLDOWN = _env_float('WAKE_WORD_COOLDOWN', 0.5)

# Recording
VAD_LEVEL = 1
FRAME_DURATION = 30
SILENCE_THRESHOLD = 0.6
MAX_RECORDING_TIME = 10.0
ADAPTIVE_SILENCE_ENABLED = _env_bool('ADAPTIVE_SILENCE_ENABLED', True)
ADAPTIVE_SILENCE_RATIO = _env_float('ADAPTIVE_SILENCE_RATIO', 1.8)
ADAPTIVE_AMBIENT_ALPHA = _env_float('ADAPTIVE_AMBIENT_ALPHA', 0.2)
ADAPTIVE_MIN_SILENCE_RMS = _env_float('ADAPTIVE_MIN_SILENCE_RMS', 300.0)
STARTUP_CALIBRATION_ENABLED = _env_bool('STARTUP_CALIBRATION_ENABLED', True)
STARTUP_CALIBRATION_SECONDS = _env_float('STARTUP_CALIBRATION_SECONDS', 2.0)

# Normalization
AUDIO_NORMALIZATION_ENABLED = _env_bool('AUDIO_NORMALIZATION_ENABLED', True)
AUDIO_TARGET_RMS = _env_float('AUDIO_TARGET_RMS', 3000.0)

# Hailo STT
HAILO_STT_MODEL = "whisper-base"

def _normalize_language(value: str) -> str:
    if not value:
        return "fr"
    lower = value.strip().lower()
    if lower.startswith("fr"):
        return "fr"
    if lower.startswith("en"):
        return "en"
    return lower

LANGUAGE = _normalize_language(_env_str('LANGUAGE', 'fr'))
STT_MAX_RETRIES = _env_int('STT_MAX_RETRIES', 3)
STT_RETRY_DELAY = _env_float('STT_RETRY_DELAY', 0.5)
STT_RETRY_BACKOFF = _env_float('STT_RETRY_BACKOFF', 2.0)
STT_LOCK_TIMEOUT = _env_float('STT_LOCK_TIMEOUT', 15.0)
STT_REBUILD_THRESHOLD = _env_int('STT_REBUILD_THRESHOLD', 2)

# STT Backend
STT_BACKEND = _env_str('STT_BACKEND', 'hailo').lower()
CPU_STT_MODEL = _env_str('CPU_STT_MODEL', 'base')
CPU_STT_LANGUAGE = _env_str('CPU_STT_LANGUAGE', LANGUAGE)

# Response Library
RESPONSE_LIBRARY_PATH = _env_str('RESPONSE_LIBRARY_PATH', f'{PROJECT_ROOT}/resources/response_library.json')
INTERACTION_LOG_PATH = _env_str('INTERACTION_LOG_PATH', f'{PROJECT_ROOT}/logs/intent_log.jsonl')
INTERACTION_LOGGER = _env_str('INTERACTION_LOGGER', 'jsonl')

# Logging outputs: comma-separated (stdout, stderr, file)
LOG_OUTPUTS = _env_str('LOG_OUTPUTS', 'stdout')
LOG_FILE_PATH = _env_str('LOG_FILE_PATH', f'{PROJECT_ROOT}/logs/pisat.log')
DEBUG_LOG_OUTPUTS = _env_str('DEBUG_LOG_OUTPUTS', 'stdout,file')
DEBUG_LOG_FILE_PATH = _env_str('DEBUG_LOG_FILE_PATH', f'{PROJECT_ROOT}/logs/pisat.debug.log')
EVENT_BUS_MAX_QUEUE = _env_int('EVENT_BUS_MAX_QUEUE', 1000)
EVENT_BUS_DROP_POLICY = _env_str('EVENT_BUS_DROP_POLICY', 'drop_new')
EVENT_BUS_ENFORCE_WHITELIST = _env_bool('EVENT_BUS_ENFORCE_WHITELIST', True)
EVENT_LOGGER = _env_str('EVENT_LOGGER', 'jsonl')
EVENT_LOG_PATH = _env_str('EVENT_LOG_PATH', f'{PROJECT_ROOT}/logs/events.jsonl')

# MPD
MPD_HOST = _env_str('MPD_HOST', 'localhost')
MPD_PORT = _env_int('MPD_PORT', 6600)
MUSIC_LIBRARY = _env_str('PISAT_MUSIC_DIR', os.path.expanduser('~/Music'))
DEFAULT_SHUFFLE_MODE = _env_bool('DEFAULT_SHUFFLE_MODE', True)
DEFAULT_REPEAT_MODE = _env_str('DEFAULT_REPEAT_MODE', 'playlist')

# Piper TTS
PIPER_MODEL_PATH = _env_str('PIPER_MODEL', f'{PROJECT_ROOT}/resources/voices/fr_FR-siwis-medium.onnx')
PIPER_BINARY_PATH = _env_str('PIPER_BINARY', '/usr/local/bin/piper')
PIPER_OUTPUT_DEVICE = _env_str('PIPER_OUTPUT_DEVICE', 'pipewire')

# Intent matching & Music search
FUZZY_MATCH_THRESHOLD = _env_int('FUZZY_MATCH_THRESHOLD', 60)  # Raised to 60 to prevent false positives
PHONETIC_WEIGHT = _env_float('PHONETIC_WEIGHT', 0.6)
INTENT_MATCH_THRESHOLD = _env_int('INTENT_MATCH_THRESHOLD', 50)
INTENT_CONTROL_THRESHOLD = _env_int('INTENT_CONTROL_THRESHOLD', 75)
INTENT_PHONETIC_WEIGHT = _env_float('INTENT_PHONETIC_WEIGHT', 0.6)
INTENT_DICTIONARY_PATH = _env_str(
    'INTENT_DICTIONARY_PATH',
    f'{PROJECT_ROOT}/resources/intent_dictionary.json'
)
ACTIVE_INTENTS = {
    'play_music',
    'pause',
    'continue',
    'volume_up',
    'volume_down',
}

# Volume
MASTER_VOLUME = _env_int('MASTER_VOLUME', 15)
VOLUME_STEP = _env_int('VOLUME_STEP', 5)
MAX_VOLUME = _env_int('MAX_VOLUME', 50)

# Sleep Timer
SLEEP_TIMER_FADE_DURATION = _env_int('SLEEP_TIMER_FADE_DURATION', 30)  # seconds

# USB Button Controller (Physical button on speaker)
USB_BUTTON_ENABLED = _env_bool('USB_BUTTON_ENABLED', True)
USB_BUTTON_DEVICE_PATH = _env_str(
    'USB_BUTTON_DEVICE_PATH',
    '/dev/input/event0'
)
USB_BUTTON_DEVICE_FILTER = _env_str('USB_BUTTON_DEVICE_FILTER', 'Jieli')
USB_BUTTON_DOUBLE_PRESS_WINDOW = _env_float('USB_BUTTON_DOUBLE_PRESS_WINDOW', 1.2)  # seconds
USB_BUTTON_DEBUG = _env_bool('USB_BUTTON_DEBUG', False)
