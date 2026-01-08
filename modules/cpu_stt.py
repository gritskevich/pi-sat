import numpy as np
import tempfile
import os
import wave
import config
from .logging_utils import setup_logger, log_info, log_warning, log_error, log_success
from .audio_file_utils import to_int16, write_wav_int16

logger = setup_logger(__name__)

try:
    from faster_whisper import WhisperModel
    CPU_WHISPER_AVAILABLE = True
except ImportError:
    CPU_WHISPER_AVAILABLE = False


class CpuSTT:
    def __init__(self, debug=False, language=None, model=None):
        self.debug = debug
        self.language = language or config.CPU_STT_LANGUAGE
        self.model = model or config.CPU_STT_MODEL
        self._model = None
        self._load_model()

    def _get_variant(self):
        if self.model.startswith("whisper-"):
            return self.model.split("-", 1)[1]
        return self.model

    def _load_model(self):
        if self._model is not None:
            return

        if not CPU_WHISPER_AVAILABLE:
            log_warning(logger, "CPU STT unavailable: faster-whisper not installed")
            return

        variant = self._get_variant()
        try:
            if self.debug:
                log_info(logger, f"Loading CPU Whisper model: {variant}")
            self._model = WhisperModel(variant, device="cpu", compute_type="int8")
            if self.debug:
                log_success(logger, f"Loaded CPU Whisper model: {variant} (language: {self.language})")
        except Exception as e:
            log_error(logger, f"Failed to load CPU Whisper model: {e}")
            self._model = None

    def transcribe(self, audio_data):
        if len(audio_data) == 0:
            return ""

        if self._model is None:
            if self.debug:
                log_warning(logger, "CPU STT not available - no model loaded")
            return ""

        tmp_path = None
        try:
            tmp_path = self._write_temp_wav(audio_data)
            segments, _info = self._model.transcribe(
                tmp_path,
                language=self.language,
                beam_size=1,
            )
            text = " ".join(segment.text for segment in segments).strip()
            return text
        except Exception as e:
            log_error(logger, f"CPU STT error: {e}")
            return ""
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

    def is_available(self):
        return self._model is not None

    def reload(self):
        self._model = None
        self._load_model()

    def cleanup(self):
        self._model = None

    def get_language(self):
        return self.language

    def _write_temp_wav(self, audio_data):
        """Write audio data to temporary WAV file, handling both bytes and numpy arrays."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            if isinstance(audio_data, bytes):
                # Bytes may be WAV or raw PCM. Detect WAV header (RIFF....WAVE)
                if len(audio_data) >= 12 and audio_data[0:4] == b"RIFF" and audio_data[8:12] == b"WAVE":
                    tmp_file.write(audio_data)
                    tmp_file.flush()
                else:
                    audio_array = np.frombuffer(audio_data, dtype=np.int16)
                    write_wav_int16(tmp_path, audio_array, config.SAMPLE_RATE)
            else:
                # Assume numpy array of PCM samples
                write_wav_int16(tmp_path, to_int16(audio_data), config.SAMPLE_RATE)
        return tmp_path
