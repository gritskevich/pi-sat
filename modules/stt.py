import logging
import numpy as np
import tempfile
import os
import sys
import time
import scipy.io.wavfile as wav
import config

logger = logging.getLogger(__name__)

class SpeechToText:
    def __init__(self):
        self.pipeline = None
        self.hailo_path = os.path.join(
            os.path.dirname(__file__), 
            "../lib/hailo-examples/runtime/hailo-8/python/speech_recognition"
        )
        self._setup_hailo_path()
        self._load_model()
        
    def _setup_hailo_path(self):
        """Add Hailo examples to Python path"""
        if self.hailo_path not in sys.path:
            sys.path.insert(0, self.hailo_path)
            
    def _load_model(self):
        logger.info("Loading Hailo STT pipeline")
        self._load_hailo_model()
            
    def _load_hailo_model(self):
        """Load Hailo Whisper pipeline"""
        try:
            # Check if Hailo examples are available
            if not os.path.exists(self.hailo_path):
                logger.error(f"Hailo examples not found at {self.hailo_path}")
                logger.info("Run setup.sh to install Hailo examples")
                self.pipeline = None
                return
                
            from app.whisper_hef_registry import HEF_REGISTRY
            from app.hailo_whisper_pipeline import HailoWhisperPipeline
            
            variant = config.HAILO_STT_MODEL.split("-")[-1]  # "whisper-small" -> "small"
            if variant not in ["tiny", "base"]:
                variant = "base"
            
            hw_arch = "hailo8"  # Default to hailo8, can be made configurable
            
            encoder_path = HEF_REGISTRY[variant][hw_arch]["encoder"]
            decoder_path = HEF_REGISTRY[variant][hw_arch]["decoder"]
            
            self.pipeline = HailoWhisperPipeline(
                encoder_path, 
                decoder_path, 
                variant, 
                multi_process_service=False
            )
            logger.info(f"Loaded Hailo Whisper {variant} model")
            
        except Exception as e:
            logger.error(f"Failed to load Hailo model: {e}")
            logger.info("Run setup.sh to install Hailo examples")
            self.pipeline = None
            
    def transcribe(self, audio_data):
        if len(audio_data) == 0:
            return ""
            
        if self.pipeline:
            return self._transcribe_hailo(audio_data)
        else:
            logger.warning("STT not available - no model loaded")
            return ""
            
    def _transcribe_hailo(self, audio_data):
        """Transcribe using Hailo pipeline"""
        try:
            # Convert int16 to float32 and save as temporary wav file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                tmp_path = tmp_file.name
                wav.write(tmp_path, config.SAMPLE_RATE, audio_data.astype(np.int16))
            
            # Use Hailo audio processing
            from common.audio_utils import load_audio
            from common.preprocessing import preprocess, improve_input_audio
            from common.postprocessing import clean_transcription
            
            # Load and preprocess audio
            sampled_audio = load_audio(tmp_path)
            sampled_audio, start_time = improve_input_audio(sampled_audio, vad=True)
            
            chunk_offset = max(0, start_time - 0.2)
            chunk_length = 10 if "tiny" in config.HAILO_STT_MODEL else 5
            
            mel_spectrograms = preprocess(
                sampled_audio,
                is_nhwc=True,
                chunk_length=chunk_length,
                chunk_offset=chunk_offset
            )
            
            # Process through pipeline
            for mel in mel_spectrograms:
                self.pipeline.send_data(mel)
                time.sleep(0.2)
                transcription = clean_transcription(self.pipeline.get_transcription())
                # Clean up temporary file
                os.unlink(tmp_path)
                return transcription.strip()
                
            # Clean up temporary file
            os.unlink(tmp_path)
            return ""
            
        except Exception as e:
            logger.error(f"Hailo STT error: {e}")
            return "" 