import logging
import numpy as np
import tempfile
import os
import sys
import scipy.io.wavfile as wav
import config

logger = logging.getLogger(__name__)

class SpeechToText:
    def __init__(self):
        self.pipeline = None
        self.speech_path = os.path.join(os.path.dirname(__file__), "../speech_recognition")
        self._setup_paths()
        self._load_model()
        
    def _setup_paths(self):
        if self.speech_path not in sys.path:
            sys.path.insert(0, self.speech_path)
            
    def _load_model(self):
        logger.info("Loading Hailo STT pipeline")
        try:
            from app.hailo_whisper_pipeline import HailoWhisperPipeline
            from app.whisper_hef_registry import HEF_REGISTRY
            
            variant = config.HAILO_STT_MODEL.split("-")[-1]
            if variant not in ["tiny", "base"]:
                variant = "base"
            
            encoder_path = os.path.join(self.speech_path, HEF_REGISTRY[variant][config.HAILO_STT_HW_ARCH]["encoder"])
            decoder_path = os.path.join(self.speech_path, HEF_REGISTRY[variant][config.HAILO_STT_HW_ARCH]["decoder"])
            
            # Store paths for lazy initialization
            self.encoder_path = encoder_path
            self.decoder_path = decoder_path
            self.variant = variant
            self.pipeline = None  # Will be initialized on first use
            
            logger.info(f"Prepared Hailo Whisper {variant} model paths")
            
        except Exception as e:
            logger.error(f"Failed to load Hailo model: {e}")
            self.pipeline = None
            
    def transcribe(self, audio_data):
        if len(audio_data) == 0:
            return ""
            
        # Lazy initialize pipeline on first use
        if self.pipeline is None:
            try:
                from app.hailo_whisper_pipeline import HailoWhisperPipeline
                self.pipeline = HailoWhisperPipeline(self.encoder_path, self.decoder_path, self.variant)
                logger.info("Hailo pipeline initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Hailo pipeline: {e}")
                return ""
            
        try:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                wav.write(tmp_file.name, config.SAMPLE_RATE, audio_data.astype(np.int16))
            
            from common.audio_utils import load_audio
            from common.preprocessing import preprocess, improve_input_audio
            from common.postprocessing import clean_transcription
            
            audio = load_audio(tmp_file.name)
            audio, start_time = improve_input_audio(audio, vad=True)
            
            chunk_length = 10 if "tiny" in config.HAILO_STT_MODEL else 5
            mel_spectrograms = preprocess(
                audio,
                is_nhwc=True,
                chunk_length=chunk_length,
                chunk_offset=max(0, start_time - 0.2)
            )
            
            for mel in mel_spectrograms:
                self.pipeline.send_data(mel)
                transcription = clean_transcription(self.pipeline.get_transcription())
                os.unlink(tmp_file.name)
                return transcription.strip()
                
            os.unlink(tmp_file.name)
            return ""
            
        except Exception as e:
            logger.error(f"Hailo STT error: {e}")
            return "" 