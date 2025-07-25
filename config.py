import os

SAMPLE_RATE = 16000
CHUNK_SIZE = 320  # 20ms frames for webrtcvad
CHANNELS = 1

WAKE_WORD_MODELS = ["alexa"]
WAKE_WORD_THRESHOLD = 0.6
WAKE_WORD_COOLDOWN = 1.0
WAKE_WORD_RESET_DELAY = 1.0

VAD_AGGRESSIVENESS = 3
SILENCE_DURATION = 1.0
INITIAL_SILENCE_TIMEOUT = 1.0
MAX_RECORDING_DURATION = 10.0

HAILO_STT_MODEL = "whisper-base"
HAILO_STT_LANGUAGE = "en"
HAILO_STT_HW_ARCH = "hailo8l"

HOME_ASSISTANT_URL = os.getenv("HA_URL", "http://homeassistant.local:8123")
HOME_ASSISTANT_TOKEN = os.getenv("HA_TOKEN", "")

TTS_ENABLED = True 