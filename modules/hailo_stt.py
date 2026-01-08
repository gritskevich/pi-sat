import numpy as np
import tempfile
import os
import sys
import time
import wave
import threading
import config
from .logging_utils import setup_logger, log_info, log_success, log_warning, log_error, log_debug, log_stt
from .audio_file_utils import to_int16, write_wav_int16

logger = setup_logger(__name__)

HAILO_PIPELINE_PROCESSING_DELAY = 0.2

class HailoSTT:
    def __init__(self, debug=False, language=None, model=None):
        self.debug = debug
        self.language = language or config.LANGUAGE
        self.model = model or config.HAILO_STT_MODEL
        self._lock = threading.Lock()  # Thread-safe pipeline access
        self._consecutive_failures = 0  # Track failures to trigger auto-rebuild
        self._pipeline = None
        self._initialized = False

        # Metrics tracking
        self._metrics = {
            'total_requests': 0,
            'successful': 0,
            'failed': 0,
            'retries': 0,
            'rebuilds': 0,
            'lock_timeouts': 0
        }
        self._last_metrics_log = time.time()

        self._setup_hailo_path()
        self._load_model(language=self.language)
        
    def _setup_hailo_path(self):
        hailo_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 
            "hailo_examples/speech_recognition"
        )
        if hailo_path not in sys.path:
            sys.path.insert(0, hailo_path)
        
    def _load_model(self, language=None):
        if self._initialized and self._pipeline is not None:
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
                self._pipeline = None
                self._initialized = False
                return

            self._pipeline = HailoWhisperPipeline(
                encoder_path,
                decoder_path,
                variant,
                multi_process_service=False,
                language=language or config.LANGUAGE,
            )

            self._initialized = True
            self.language = language or config.LANGUAGE

            if self.debug:
                log_success(logger, f"Loaded Hailo Whisper {variant} model (language: {self.language})")

        except Exception as e:
            log_error(logger, f"Failed to load Hailo model: {e}")
            self._pipeline = None
            self._initialized = False
            
    def transcribe(self, audio_data):
        if len(audio_data) == 0:
            return ""

        if not self._pipeline:
            if self.debug:
                log_warning(logger, "STT not available - no model loaded")
            return ""

        self._metrics['total_requests'] += 1
        result = self._transcribe_with_retry(audio_data)

        # Log metrics every 50 requests (not too spammy)
        if self._metrics['total_requests'] % 50 == 0:
            self._log_metrics()

        return result
    
    def _transcribe_with_retry(self, audio_data):
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
                    self._consecutive_failures = 0  # Reset on success
                    self._metrics['successful'] += 1
                    if attempt > 0:
                        log_success(logger, f"STT succeeded after {attempt} retries")
                        self._metrics['retries'] += attempt
                    return result
                
                if attempt < max_retries:
                    attempt += 1
                    delay = min(initial_delay * (backoff_factor ** (attempt - 1)), 2.0)
                    time.sleep(delay)
                    continue
                else:
                    self._handle_failure("empty transcription after all retries")
                    self._metrics['failed'] += 1
                    return ""
                    
            except (RuntimeError, ConnectionError, OSError, IOError) as e:
                log_warning(logger, f"STT transient error (attempt {attempt + 1}/{max_retries + 1}): {e}")
                
                if attempt < max_retries:
                    attempt += 1
                    delay = min(initial_delay * (backoff_factor ** (attempt - 1)), 2.0)
                    time.sleep(delay)
                    continue
                else:
                    self._handle_failure(f"failed after {max_retries + 1} attempts: {e}")
                    return ""
            
            except Exception as e:
                log_error(logger, f"STT non-retryable error: {e}")
                self._handle_failure(f"non-retryable error: {e}")
                return ""
        
        return ""
    
    def _handle_failure(self, reason):
        self._consecutive_failures += 1
        log_warning(logger, f"STT {reason} (consecutive failures: {self._consecutive_failures})")
        self._maybe_rebuild_pipeline()
            
    def _transcribe_hailo(self, audio_data):
        tmp_path = None
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
                return ""

            # Thread-safe access to pipeline with timeout (prevents deadlock)
            acquired = self._lock.acquire(timeout=config.STT_LOCK_TIMEOUT)
            if not acquired:
                log_error(logger, f"Hailo pipeline lock timeout ({config.STT_LOCK_TIMEOUT}s) - possible hardware hang")
                self._consecutive_failures += 1
                self._metrics['lock_timeouts'] += 1
                self._maybe_rebuild_pipeline()
                return ""

            try:
                for mel in mel_spectrograms:
                    self._pipeline.send_data(mel)
                    time.sleep(HAILO_PIPELINE_PROCESSING_DELAY)
                    raw = self._pipeline.get_transcription()
                    transcription = clean_transcription(raw).strip()

                    # Success - reset failure counter
                    self._consecutive_failures = 0

                    if transcription:
                        log_stt(logger, f"{transcription}")
                    else:
                        if self.debug:
                            log_warning(logger, "STT returned empty transcription")
                    return transcription
            finally:
                self._lock.release()

            return ""

        except Exception as e:
            log_error(logger, f"Hailo STT error: {e}")
            return ""
        finally:
            # Guaranteed temp file cleanup - even on lock timeout or exception
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception as cleanup_error:
                    # Silently ignore cleanup errors (file already deleted, permission issue, etc.)
                    pass
    
    def is_available(self):
        return self._pipeline is not None

    def _maybe_rebuild_pipeline(self):
        """Rebuild pipeline if consecutive failures exceed threshold"""
        if self._consecutive_failures >= config.STT_REBUILD_THRESHOLD:
            log_warning(logger, f"Rebuilding Hailo pipeline after {self._consecutive_failures} consecutive failures")
            self._consecutive_failures = 0
            self._metrics['rebuilds'] += 1
            try:
                self.cleanup()
            except (RuntimeError, OSError) as e:
                log_warning(logger, f"Error during pipeline cleanup (continuing): {e}")
            except Exception as e:
                log_error(logger, f"Unexpected error during pipeline cleanup: {e}")
            self._load_model(language=self.language)

    def _log_metrics(self):
        """Log STT performance metrics"""
        m = self._metrics
        total = m['total_requests']
        if total == 0:
            return

        success_rate = (m['successful'] / total) * 100
        failure_rate = (m['failed'] / total) * 100
        avg_retries = m['retries'] / m['successful'] if m['successful'] > 0 else 0

        log_info(logger,
            f"STT Metrics: {total} requests | "
            f"Success: {success_rate:.1f}% | "
            f"Failed: {failure_rate:.1f}% | "
            f"Avg retries: {avg_retries:.2f} | "
            f"Rebuilds: {m['rebuilds']} | "
            f"Lock timeouts: {m['lock_timeouts']}"
        )

    def reload(self):
        """Force reload the model"""
        if self.debug:
            log_info(logger, "Reloading Hailo STT model...")

        self._initialized = False
        self._pipeline = None
        # Preserve language preference if already set
        self._load_model(language=self.language)

        if self.debug:
            if self._pipeline is not None:
                log_success(logger, "Hailo STT model reloaded successfully")
            else:
                log_warning(logger, "Hailo STT model reload failed")
    
    def cleanup(self):
        """Clean up Hailo pipeline resources"""
        if self._pipeline:
            try:
                # Try graceful stop with timeout safety via background thread
                try:
                    self._pipeline.stop()
                except (RuntimeError, AttributeError) as e:
                    # Pipeline already stopped or not initialized properly
                    if self.debug:
                        log_debug(logger, f"Pipeline stop issue (ignoring): {e}")
                except Exception as e:
                    log_warning(logger, f"Unexpected error stopping pipeline: {e}")

                self._pipeline = None
                self._initialized = False
                if self.debug:
                    log_info(logger, "Hailo pipeline cleaned up")
            except Exception as e:
                log_error(logger, f"Error cleaning up Hailo pipeline: {e}")
        else:
            if self.debug:
                log_info(logger, "No Hailo pipeline to clean up")

    def get_language(self):
        return self.language
    
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
        variant = self.model.split("-")[-1]
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

    def _get_chunk_length(self):
        # Match Hailo example: base=5s, tiny=10s
        variant = self._get_variant()
        return 10 if variant == "tiny" else 5
