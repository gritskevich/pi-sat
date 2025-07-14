import logging
import numpy as np
import soundfile as sf
import io
import config

logger = logging.getLogger(__name__)

class HailoSTT:
    def __init__(self):
        self.model = None
        self.use_hailo = config.HAILO_STT_USE_HAILO
        self._load_model()
        
    def _load_model(self):
        if self.use_hailo:
            try:
                self._load_hailo_model()
                logger.info("Hailo STT model loaded successfully")
            except Exception as e:
                logger.warning(f"Hailo STT failed: {e}, falling back to CPU")
                self.use_hailo = False
                self._load_cpu_model()
        else:
            self._load_cpu_model()
            
    def _load_hailo_model(self):
        try:
            import hailo_platform
            from hailo_model_zoo import HailoModel
            self.model = HailoModel(config.HAILO_STT_MODEL)
            logger.info(f"Loaded Hailo {config.HAILO_STT_MODEL}")
        except ImportError:
            raise Exception("Hailo libraries not available")
            
    def _load_cpu_model(self):
        try:
            import whisper
            self.model = whisper.load_model("base")
            logger.info(f"Loaded CPU Whisper model")
        except ImportError:
            raise Exception("Whisper not available, install: pip install openai-whisper")
            
    def transcribe(self, audio_data):
        if len(audio_data) == 0:
            return ""
            
        try:
            if self.use_hailo:
                return self._transcribe_hailo(audio_data)
            else:
                return self._transcribe_cpu(audio_data)
        except Exception as e:
            logger.error(f"STT error: {e}")
            return ""
            
    def _transcribe_hailo(self, audio_data):
        audio_float = audio_data.astype(np.float32) / 32768.0
        result = self.model.predict(audio_float)
        return result.get("text", "").strip()
        
    def _transcribe_cpu(self, audio_data):
        audio_float = audio_data.astype(np.float32) / 32768.0
        result = self.model.transcribe(audio_float, language=config.HAILO_STT_LANGUAGE)
        return result["text"].strip() 