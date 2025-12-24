import numpy as np
import tempfile
import os
import sys
import time
import wave
import threading
import config
from .logging_utils import setup_logger, log_info, log_success, log_warning, log_error, log_debug, log_stt
from .retry_utils import retry_transient_errors

logger = setup_logger(__name__)

# Pipeline processing delay (seconds) - allows Hailo hardware to process data
HAILO_PIPELINE_PROCESSING_DELAY = 0.2

class HailoSTT:
    _instance = None
    _pipeline = None
    _initialized = False
    _language = None
    _lock = threading.Lock()  # Thread-safe singleton creation and pipeline access

    def __new__(cls, debug=False, language=None):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(HailoSTT, cls).__new__(cls)
                cls._instance.debug = debug
                cls._instance._setup_hailo_path()
                cls._instance._load_model(language=language)
            else:
                # Update runtime flags on existing singleton
                cls._instance.debug = debug
                if language and language != HailoSTT._language:
                    # Switching language requires rebuilding the pipeline
                    try:
                        cls._instance.cleanup()
                    except Exception:
                        pass
                    cls._instance._load_model(language=language)
            return cls._instance
    
    def __init__(self, debug=False, language=None):
        # Already initialized in __new__
        pass
        
    def _setup_hailo_path(self):
        hailo_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 
            "hailo_examples/speech_recognition"
        )
        if hailo_path not in sys.path:
            sys.path.insert(0, hailo_path)
        
    def _load_model(self, language=None):
        if HailoSTT._initialized and HailoSTT._pipeline is not None:
            return
            
        if self.debug:
            log_info(logger, "Loading Hailo STT pipeline")
        
        try:
            from app.hailo_whisper_pipeline import HailoWhisperPipeline
            variant = self._get_variant()
            encoder_path, decoder_path = self._select_hef_paths(variant)
            if not (os.path.exists(encoder_path) and os.path.exists(decoder_path)):
                log_warning(
                    logger,
                    f"Hailo model files not found for variant '{variant}':\n encoder: {encoder_path}\n decoder: {decoder_path}"
                )
                HailoSTT._pipeline = None
                HailoSTT._initialized = False
                HailoSTT._language = None
                return

            HailoSTT._pipeline = HailoWhisperPipeline(
                encoder_path,
                decoder_path,
                variant,
                multi_process_service=False,
                language=language or config.HAILO_STT_LANGUAGE,
            )
            
            HailoSTT._initialized = True
            HailoSTT._language = language or config.HAILO_STT_LANGUAGE

            if self.debug:
                log_success(logger, f"Loaded Hailo Whisper {variant} model (language: {HailoSTT._language})")
            
        except Exception as e:
            log_error(logger, f"Failed to load Hailo model: {e}")
            HailoSTT._pipeline = None
            HailoSTT._initialized = False
            HailoSTT._language = None
            
    def transcribe(self, audio_data):
        if len(audio_data) == 0:
            return ""
        
        if not HailoSTT._pipeline:
            if self.debug:
                log_warning(logger, "STT not available - no model loaded")
            return ""
        
        return self._transcribe_with_retry(audio_data)
    
    def _transcribe_with_retry(self, audio_data):
        """Transcribe audio with retry logic for transient errors"""
        max_retries = config.STT_MAX_RETRIES
        initial_delay = config.STT_RETRY_DELAY
        backoff_factor = config.STT_RETRY_BACKOFF
        attempt = 0
        
        while attempt <= max_retries:
            try:
                if attempt > 0:
                    log_warning(logger, f"STT retry attempt {attempt}/{max_retries}")
                
                result = self._transcribe_hailo(audio_data)
                
                if result:
                    if attempt > 0:
                        log_success(logger, f"STT succeeded after {attempt} retries")
                    return result
                
                if attempt < max_retries:
                    attempt += 1
                    delay = min(initial_delay * (backoff_factor ** (attempt - 1)), 2.0)
                    time.sleep(delay)
                    continue
                else:
                    log_warning(logger, "STT returned empty transcription after all retries")
                    return ""
                    
            except (RuntimeError, ConnectionError, OSError, IOError) as e:
                log_warning(logger, f"STT transient error (attempt {attempt + 1}/{max_retries + 1}): {e}")
                
                if attempt < max_retries:
                    attempt += 1
                    delay = min(initial_delay * (backoff_factor ** (attempt - 1)), 2.0)
                    time.sleep(delay)
                    continue
                else:
                    log_error(logger, f"STT failed after {max_retries + 1} attempts: {e}")
                    return ""
            
            except Exception as e:
                log_error(logger, f"STT non-retryable error: {e}")
                return ""
        
        return ""
            
    def _transcribe_hailo(self, audio_data):
        try:
            tmp_path = self._write_temp_wav(audio_data)
            
            from common.audio_utils import load_audio
            from common.preprocessing import preprocess, improve_input_audio
            from common.postprocessing import clean_transcription
            
            sampled_audio = load_audio(tmp_path)
            sampled_audio, start_time = improve_input_audio(sampled_audio, vad=True)
            
            # Handle None start_time
            if start_time is None:
                start_time = 0.0
            
            chunk_offset = max(0, start_time - 0.2)
            chunk_length = self._get_chunk_length()
            
            mel_spectrograms = preprocess(
                sampled_audio,
                is_nhwc=True,
                chunk_length=chunk_length,
                chunk_offset=chunk_offset
            )
            
            if not mel_spectrograms:
                os.unlink(tmp_path)
                return ""
            
            try:
                # Thread-safe access to shared pipeline (Hailo hardware not thread-safe)
                with HailoSTT._lock:
                    for mel in mel_spectrograms:
                        HailoSTT._pipeline.send_data(mel)
                        # Give pipeline time to process data (required by Hailo hardware)
                        time.sleep(HAILO_PIPELINE_PROCESSING_DELAY)
                        raw = HailoSTT._pipeline.get_transcription()
                        transcription = clean_transcription(raw).strip()
                        if transcription:
                            log_stt(logger, f"{transcription}")
                        else:
                            if self.debug:
                                log_warning(logger, "STT returned empty transcription")
                        return transcription
            finally:
                os.unlink(tmp_path)
            
            return ""
                
        except Exception as e:
            log_error(logger, f"Hailo STT error: {e}")
            return ""
    
    def is_available(self):
        return HailoSTT._pipeline is not None
    
    def reload(self):
        """Force reload the model"""
        if self.debug:
            log_info(logger, "Reloading Hailo STT model...")
        
        HailoSTT._initialized = False
        HailoSTT._pipeline = None
        # Preserve language preference if already set
        self._load_model(language=HailoSTT._language)
        
        if self.debug:
            if HailoSTT._pipeline is not None:
                log_success(logger, "Hailo STT model reloaded successfully")
            else:
                log_warning(logger, "Hailo STT model reload failed")
    
    def cleanup(self):
        """Clean up Hailo pipeline resources"""
        if HailoSTT._pipeline:
            try:
                # Try graceful stop with timeout safety via background thread
                try:
                    HailoSTT._pipeline.stop()
                except Exception:
                    pass
                HailoSTT._pipeline = None
                HailoSTT._initialized = False
                HailoSTT._language = None
                if self.debug:
                    log_info(logger, "Hailo pipeline cleaned up")
            except Exception as e:
                log_error(logger, f"Error cleaning up Hailo pipeline: {e}")
        else:
            if self.debug:
                log_info(logger, "No Hailo pipeline to clean up")

    def get_language(self):
        return HailoSTT._language
    
    def __del__(self):
        """Destructor to ensure cleanup"""
        try:
            # Don't call cleanup in destructor to avoid hanging
            pass
        except Exception as e:
            # Ignore errors during cleanup but catch specifically
            pass 

    # ---- helpers (no functional change) ----
    def _get_variant(self):
        variant = config.HAILO_STT_MODEL.split("-")[-1]
        return variant if variant in ("tiny", "base") else "base"

    def _select_hef_paths(self, variant):
        from app.whisper_hef_registry import HEF_REGISTRY
        possible_arches = ("hailo8l", "hailo8")
        base_path = os.path.dirname(os.path.dirname(__file__))
        hailo_base = os.path.join(base_path, "hailo_examples/speech_recognition")

        for arch in possible_arches:
            try:
                enc = os.path.join(hailo_base, HEF_REGISTRY[variant][arch]["encoder"])
                dec = os.path.join(hailo_base, HEF_REGISTRY[variant][arch]["decoder"])
            except KeyError:
                continue
            if os.path.exists(enc) and os.path.exists(dec):
                return enc, dec

        # Default to hailo8l paths for messaging when not found
        arch = "hailo8l"
        enc = os.path.join(hailo_base, HEF_REGISTRY[variant][arch]["encoder"])
        dec = os.path.join(hailo_base, HEF_REGISTRY[variant][arch]["decoder"])
        return enc, dec

    def _write_temp_wav(self, audio_data):
        def _to_int16(samples):
            arr = np.asarray(samples)
            if arr.dtype == np.int16:
                return arr
            if np.issubdtype(arr.dtype, np.floating):
                arr = np.clip(arr, -1.0, 1.0)
                return (arr * 32767.0).astype(np.int16)
            return arr.astype(np.int16)

        def _write_wav_int16(path: str, samples_i16: np.ndarray, rate: int):
            with wave.open(path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(int(rate))
                wf.writeframes(samples_i16.astype(np.int16, copy=False).tobytes())

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            if isinstance(audio_data, bytes):
                # Bytes may be WAV or raw PCM. Detect WAV header (RIFF....WAVE)
                if len(audio_data) >= 12 and audio_data[0:4] == b"RIFF" and audio_data[8:12] == b"WAVE":
                    tmp_file.write(audio_data)
                    tmp_file.flush()
                else:
                    audio_array = np.frombuffer(audio_data, dtype=np.int16)
                    _write_wav_int16(tmp_path, audio_array, config.SAMPLE_RATE)
            else:
                # Assume numpy array of PCM samples
                _write_wav_int16(tmp_path, _to_int16(audio_data), config.SAMPLE_RATE)
        return tmp_path

    def _get_chunk_length(self):
        # Match Hailo example: base=5s, tiny=10s
        variant = self._get_variant()
        return 10 if variant == "tiny" else 5
