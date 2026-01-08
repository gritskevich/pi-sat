import numpy as np
import time
import config
from modules.logging_utils import setup_logger, log_info, log_success, log_warning, log_error, log_debug, log_wake
from modules.audio_player import play_wake_sound
from modules.wake_word_utils import reset_wake_word_model

try:
    import pyaudio
except ModuleNotFoundError:  # optional for non-live/test environments
    pyaudio = None

try:
    from openwakeword.model import Model
    import openwakeword.utils as openwakeword_utils
except ModuleNotFoundError:  # optional dependency; required to instantiate
    Model = None
    openwakeword_utils = None


class WakeWordListener:
    def __init__(self, debug=False):
        if Model is None or openwakeword_utils is None:
            raise RuntimeError(
                "openwakeword is not installed. Install dependencies via `./pi-sat.sh install` "
                "or `pip install openwakeword`."
            )

        openwakeword_utils.download_models()

        self.debug = debug
        self.logger = setup_logger(__name__, debug=debug)

        if config.ENABLE_SPEEX_NOISE_SUPPRESSION:
            log_info(self.logger, "Speex noise suppression: ENABLED")
        else:
            log_info(self.logger, "Speex noise suppression: DISABLED")

        self.model = Model(
            wakeword_models=config.WAKE_WORD_MODELS,
            inference_framework=config.INFERENCE_FRAMEWORK,
            vad_threshold=config.VAD_THRESHOLD,  # Voice Activity Detection (0.6 = balanced, 0.7+ = strict)
            enable_speex_noise_suppression=config.ENABLE_SPEEX_NOISE_SUPPRESSION
        )

        self.p = None
        self.stream = None
        self.last_detection_time = 0
        self.cooldown = float(getattr(config, "WAKE_WORD_COOLDOWN", 2.0))
        self.tts_cooldown_end = 0
        self.running = True
        self._heartbeat_counter = 0
        self._last_model_reset = time.time()
        self._last_debug_log = time.time()
        self._debug_log_interval = 0.5

    def _flush_stream_buffer(self):
        """Drop any buffered audio collected while command processing blocked detection."""
        if not self.stream:
            return
        try:
            if hasattr(self.stream, "get_read_available"):
                available = int(self.stream.get_read_available())
                if available > 0:
                    self.stream.read(available, exception_on_overflow=False)
        except Exception as e:
            log_debug(self.logger, f"Failed to flush stream buffer: {e}")
        
    def reset_model_state(self):
        """Reset wake word model state by feeding it silence."""
        reset_wake_word_model(self.model)
        
    def start_listening(self):
        if pyaudio is None:
            raise RuntimeError("pyaudio is not installed; live listening is unavailable")

        if self.p is None:
            self.p = pyaudio.PyAudio()
        target_rate = int(getattr(config, "RATE", 16000))
        model_rate = 16000
        self._resample_buf = np.zeros(0, dtype=np.int16)
        try:
            self.stream = self.p.open(
                format=getattr(pyaudio, config.FORMAT),
                channels=config.CHANNELS,
                rate=target_rate,
                input=True,
                input_device_index=None,
                frames_per_buffer=config.CHUNK
            )
            self._input_rate = target_rate
            time.sleep(0.1)
        except Exception as e:
            log_warning(self.logger, f"Failed to open stream at {target_rate}Hz, trying fallback: {e}")
            try:
                info = self.p.get_default_input_device_info()
                fallback_rate = int(info.get("defaultSampleRate", 16000))
            except Exception as fallback_err:
                log_warning(self.logger, f"Failed to get default device info: {fallback_err}")
                fallback_rate = 48000
            self.stream = self.p.open(
                format=getattr(pyaudio, config.FORMAT),
                channels=config.CHANNELS,
                rate=fallback_rate,
                input=True,
                input_device_index=None,
                frames_per_buffer=config.CHUNK
            )
            self._input_rate = fallback_rate
            time.sleep(0.1)
        
        log_info(self.logger, "Wake word listener started...")

        while self.running:
            try:
                self._heartbeat_counter += 1
                if self._heartbeat_counter % 600 == 0:
                    log_debug(self.logger, f"Wake word listener alive (iterations: {self._heartbeat_counter})")
                
                if time.time() - self._last_model_reset > 60.0:
                    self.reset_model_state()
                    self._last_model_reset = time.time()
                    log_debug(self.logger, "Wake word model state reset (60s periodic)")

                data = self.stream.read(config.CHUNK, exception_on_overflow=False)
                audio = np.frombuffer(data, dtype=np.int16)

                if getattr(self, "_input_rate", target_rate) != model_rate and audio.size > 0:
                    src = audio.astype(np.float32)
                    src_len = src.shape[0]
                    ratio = model_rate / float(self._input_rate)
                    new_len = max(1, int(round(src_len * ratio)))
                    x_old = np.linspace(0.0, 1.0, num=src_len, dtype=np.float32)
                    x_new = np.linspace(0.0, 1.0, num=new_len, dtype=np.float32)
                    resampled = np.interp(x_new, x_old, src)
                    audio = np.clip(resampled, -32768, 32767).astype(np.int16)

                if audio.size > 0:
                    self._resample_buf = np.concatenate((self._resample_buf, audio))
                frame_size = 320
                while self._resample_buf.size >= frame_size:
                    frame = self._resample_buf[:frame_size]
                    self._resample_buf = self._resample_buf[frame_size:]

                    if self.debug:
                        rms = float(np.sqrt(np.mean(frame.astype(np.float32) ** 2)))

                    try:
                        prediction = self.model.predict(frame)
                    except Exception as pred_error:
                        log_warning(self.logger, f"Model prediction error: {pred_error}")
                        # Reset and skip this frame
                        self.reset_model_state()
                        continue

                    if self.debug and time.time() - self._last_debug_log >= self._debug_log_interval:
                        confidence_str = ", ".join([f"{ww}: {conf:.3f}" for ww, conf in prediction.items()])
                        log_debug(self.logger, f"🎤 RMS: {rms:>6.1f} | Confidences: {confidence_str}")
                        self._last_debug_log = time.time()

                    for wake_word, confidence in prediction.items():
                        if confidence > config.THRESHOLD:
                            current_time = time.time()

                            if current_time < self.tts_cooldown_end:
                                if self.debug:
                                    remaining = self.tts_cooldown_end - current_time
                                    log_debug(self.logger, f"🔇 Ignoring detection during TTS cooldown ({remaining:.1f}s remaining)")
                                continue

                            if current_time - self.last_detection_time >= self.cooldown:
                                self.last_detection_time = current_time
                                log_success(self.logger, f"🔔 WAKE WORD: {wake_word} ({confidence:.2f})")
                                play_wake_sound()

                                log_debug(self.logger, "Closing audio stream for command processing...")
                                if self.stream:
                                    self.stream.stop_stream()
                                    self.stream.close()
                                    self.stream = None

                                try:
                                    self._notify_orchestrator()
                                except Exception as notify_error:
                                    log_error(self.logger, f"Command processing error: {notify_error}")

                                log_debug(self.logger, "Recreating audio stream for wake word detection...")
                                # Retry stream recreation up to 3 times
                                stream_recreated = False
                                for retry in range(3):
                                    try:
                                        time.sleep(0.1 * (retry + 1))  # Increasing backoff

                                        self.stream = self.p.open(
                                            format=getattr(pyaudio, config.FORMAT),
                                            channels=config.CHANNELS,
                                            rate=self._input_rate,
                                            input=True,
                                            input_device_index=None,
                                            frames_per_buffer=config.CHUNK
                                        )

                                        self._resample_buf = np.zeros(0, dtype=np.int16)
                                        self.reset_model_state()

                                        log_debug(self.logger, "Audio stream recreated successfully")
                                        stream_recreated = True
                                        break
                                    except Exception as stream_error:
                                        if retry < 2:
                                            log_warning(self.logger, f"Stream recreation attempt {retry + 1} failed: {stream_error}, retrying...")
                                        else:
                                            log_error(self.logger, f"Stream recreation failed after 3 attempts: {stream_error}")

                                if not stream_recreated:
                                    log_error(self.logger, "Stopping wake word detection due to stream recreation failure")
                                    self.running = False
                                    break
                        elif self.debug and confidence > config.LOW_CONFIDENCE_THRESHOLD:
                            log_debug(self.logger, f"👂 Low confidence: {wake_word} ({confidence:.2f})")
                
                time.sleep(0.001)
                            
            except KeyboardInterrupt:
                break
            except Exception as e:
                log_error(self.logger, f"Wake word listener error: {e}")
                try:
                    self._resample_buf = np.zeros(0, dtype=np.int16)
                    self.reset_model_state()
                    log_warning(self.logger, "Attempting to recover wake word detection...")
                    time.sleep(0.5)
                except Exception as recovery_error:
                    log_error(self.logger, f"Recovery failed: {recovery_error}")
                    break

        self.stop_listening()
    
    def _notify_orchestrator(self):
        log_debug(self.logger, "Notifying orchestrator...")

    def stop_listening(self):
        self.running = False
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        if self.p:
            self.p.terminate()
            self.p = None
        log_info(self.logger, "Wake word listener stopped.")

    def detect_wake_word(self, audio_data):
        if len(audio_data) == 0:
            return False
        
        if audio_data.dtype != np.int16:
            audio_data = (audio_data * 32767).astype(np.int16)
        
        chunk_size = config.CHUNK
        detected = False
        
        for i in range(0, len(audio_data), chunk_size):
            chunk = audio_data[i:i+chunk_size]
            if len(chunk) < chunk_size:
                chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
            
            prediction = self.model.predict(chunk)
            
            for wake_word, confidence in prediction.items():
                if confidence > config.THRESHOLD:
                    detected = True
                    break
            
            if detected:
                break
        
        return detected

if __name__ == "__main__":
    listener = WakeWordListener()
    try:
        listener.start_listening()
    except KeyboardInterrupt:
        listener.stop_listening()
        try:
            sys.exit(0)
        except SystemExit:
            pass 
