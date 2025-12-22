import numpy as np
import time
import config
from modules.logging_utils import setup_logger, log_info, log_success, log_warning, log_error, log_debug, log_wake
from modules.audio_player import play_wake_sound

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

        # Initialize openWakeWord with optimizations:
        # - vad_threshold: Requires Silero VAD to detect speech (reduces false positives)
        # - enable_speex_noise_suppression: Reduces background noise (Linux only)
        # See: https://github.com/dscripka/openWakeWord for details
        self.model = Model(
            wakeword_models=config.WAKE_WORD_MODELS,
            inference_framework=config.INFERENCE_FRAMEWORK,
            vad_threshold=config.VAD_THRESHOLD,  # Voice Activity Detection (0.6 = balanced, 0.7+ = strict)
            enable_speex_noise_suppression=config.ENABLE_SPEEX_NOISE_SUPPRESSION
        )

        # Lazily create PyAudio only when starting live listening to avoid lingering threads during tests
        self.p = None
        self.stream = None
        self.last_detection_time = 0
        self.cooldown = float(getattr(config, "WAKE_WORD_COOLDOWN", 2.0))
        self.debug = debug
        self.running = True
        self.logger = setup_logger(__name__, debug=debug)

    def _flush_stream_buffer(self):
        """Drop any buffered audio collected while command processing blocked detection."""
        if not self.stream:
            return
        try:
            if hasattr(self.stream, "get_read_available"):
                available = int(self.stream.get_read_available())
                if available > 0:
                    self.stream.read(available, exception_on_overflow=False)
        except Exception:
            pass
        
    def reset_model_state(self):
        silence = np.zeros(config.CHUNK * 25, dtype=np.int16)
        for _ in range(2):
            self.model.predict(silence)
        
    def start_listening(self):
        if pyaudio is None:
            raise RuntimeError("pyaudio is not installed; live listening is unavailable")

        if self.p is None:
            self.p = pyaudio.PyAudio()
        target_rate = int(getattr(config, "RATE", 16000))  # device open rate
        model_rate = 16000  # openWakeWord expects 16kHz
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
        except Exception:
            # Fallback to default device rate, will resample in software
            try:
                info = self.p.get_default_input_device_info()
                fallback_rate = int(info.get("defaultSampleRate", 16000))
            except Exception:
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
                data = self.stream.read(config.CHUNK, exception_on_overflow=False)
                audio = np.frombuffer(data, dtype=np.int16)

                # Resample device audio to 16 kHz for the model if needed
                if getattr(self, "_input_rate", target_rate) != model_rate and audio.size > 0:
                    src = audio.astype(np.float32)
                    src_len = src.shape[0]
                    ratio = model_rate / float(self._input_rate)
                    new_len = max(1, int(round(src_len * ratio)))
                    x_old = np.linspace(0.0, 1.0, num=src_len, dtype=np.float32)
                    x_new = np.linspace(0.0, 1.0, num=new_len, dtype=np.float32)
                    resampled = np.interp(x_new, x_old, src)
                    audio = np.clip(resampled, -32768, 32767).astype(np.int16)

                # Accumulate and process fixed 20ms (320 @16k) chunks
                if audio.size > 0:
                    self._resample_buf = np.concatenate((self._resample_buf, audio))
                # Use 20ms frames at 16kHz (320 samples) for prediction
                frame_size = 320
                while self._resample_buf.size >= frame_size:
                    frame = self._resample_buf[:frame_size]
                    self._resample_buf = self._resample_buf[frame_size:]

                    prediction = self.model.predict(frame)
                    for wake_word, confidence in prediction.items():
                        if confidence > config.THRESHOLD:
                            current_time = time.time()
                            if current_time - self.last_detection_time >= self.cooldown:
                                self.last_detection_time = current_time
                                log_success(self.logger, f"🔔 WAKE WORD: {wake_word} ({confidence:.2f})")
                                # Play confirmation sound (non-blocking)
                                play_wake_sound()
                                # Reset model state before notification
                                self.reset_model_state()
                                # Notify orchestrator with stream context (this will block until command processing completes)
                                # Pass stream and input rate for immediate recording (eliminates stream creation latency)
                                self._notify_orchestrator(stream=self.stream, input_rate=self._input_rate)
                                # Soft cooldown starts AFTER command processing (prevents immediate re-trigger from buffered audio)
                                self._flush_stream_buffer()
                                self._resample_buf = np.zeros(0, dtype=np.int16)
                                self.reset_model_state()
                                self.last_detection_time = time.time()
                                # Note: timestamp-based cooldown prevents duplicate detections
                        elif self.debug and confidence > config.LOW_CONFIDENCE_THRESHOLD:
                            log_debug(self.logger, f"👂 Low confidence: {wake_word} ({confidence:.2f})")
                    # small sleep to yield CPU in tight loop
                    time.sleep(0.005)
                            
            except KeyboardInterrupt:
                break
            except Exception as e:
                log_error(self.logger, f"Wake word listener error: {e}")
                break
                
        self.stop_listening()
    
    def _notify_orchestrator(self, stream=None, input_rate=None):
        """
        Notify orchestrator of wake word detection.

        Args:
            stream: Active PyAudio stream (for reuse, eliminates latency)
            input_rate: Stream sample rate

        This method is overridden by orchestrator to provide actual handling.
        """
        log_debug(self.logger, "Notifying orchestrator with stream context...")
        
    def _pause_detection(self):
        log_debug(self.logger, "Pausing detection for 2 seconds...")
        self.reset_model_state()
        time.sleep(self.cooldown)
        
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
        """Detect wake word in audio data (for testing)"""
        if len(audio_data) == 0:
            return False
        
        # Convert to int16 if needed
        if audio_data.dtype != np.int16:
            audio_data = (audio_data * 32767).astype(np.int16)
        
        # Process in chunks
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
