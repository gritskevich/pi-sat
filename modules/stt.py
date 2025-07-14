import logging
import numpy as np
import tempfile
import subprocess
import os
import scipy.io.wavfile as wav
import config

logger = logging.getLogger(__name__)

class SpeechToText:
    def __init__(self):
        self.model = None
        self.use_hailo = config.HAILO_STT_USE_HAILO
        self.hailo_script_path = os.path.join(
            os.path.dirname(__file__), 
            "../lib/hailo-examples/runtime/hailo-8/python/speech_recognition"
        )
        self.hailo_python = os.path.join(self.hailo_script_path, "whisper_env/bin/python")
        self.hailo_wrapper = os.path.join(self.hailo_script_path, "hailo_stt_wrapper.py")
        self._load_model()
        
    def _load_model(self):
        if self.use_hailo:
            logger.info("Hailo STT enabled - using external Hailo pipeline")
            self._check_hailo_setup()
        else:
            self._load_whisper_model()
            
    def _check_hailo_setup(self):
        """Check if Hailo setup is available"""
        if not os.path.exists(self.hailo_python):
            logger.warning(f"Hailo Python not found at {self.hailo_python}")
        if not os.path.exists(self.hailo_wrapper):
            logger.warning(f"Hailo wrapper not found at {self.hailo_wrapper}")
            
    def _load_whisper_model(self):
        try:
            import whisper
            self.model = whisper.load_model("base")
            logger.info("Loaded Whisper model")
        except ImportError:
            raise Exception("Whisper not available, install: pip install openai-whisper")
            
    def transcribe(self, audio_data):
        if len(audio_data) == 0:
            return ""
            
        if self.use_hailo:
            return self._transcribe_hailo(audio_data)
        else:
            return self._transcribe_whisper(audio_data)
            
    def _transcribe_hailo(self, audio_data):
        """Transcribe using Hailo pipeline via external script"""
        try:
            # Save audio to temporary file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                tmp_path = tmp_file.name
                wav.write(tmp_path, config.SAMPLE_RATE, audio_data.astype(np.int16))
            
            # Call Hailo wrapper script
            cmd = [
                self.hailo_python, 
                self.hailo_wrapper, 
                tmp_path,
                "--variant", config.HAILO_STT_MODEL.split("-")[-1],  # "whisper-small" -> "small", "whisper-base" -> "base"
            ]
            
            result = subprocess.run(
                cmd, 
                cwd=self.hailo_script_path,
                capture_output=True, 
                text=True, 
                timeout=30
            )
            
            # Clean up temporary file
            os.unlink(tmp_path)
            
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                logger.error(f"Hailo STT error: {result.stderr}")
                return ""
                
        except Exception as e:
            logger.error(f"Hailo STT error: {e}")
            return ""
            
    def _transcribe_whisper(self, audio_data):
        try:
            audio_float = audio_data.astype(np.float32) / 32768.0
            result = self.model.transcribe(audio_float, language=config.HAILO_STT_LANGUAGE)
            return result["text"].strip()
        except Exception as e:
            logger.error(f"STT error: {e}")
            return "" 