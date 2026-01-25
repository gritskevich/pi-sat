import numpy as np
import sys
import time
import threading
import queue
import config
from modules.base_module import BaseModule
from modules.logging_utils import log_info, log_success, log_warning, log_error, log_debug, log_wake
from modules.audio_player import play_wake_sound
from modules.audio_devices import find_input_device_index
from modules.alsa_utils import suppress_alsa_errors, suppress_jack_autostart, suppress_stderr
from modules.control_events import ControlEvent, EVENT_WAKE_WORD_DETECTED, EVENT_RECORDING_FINISHED

WAKE_WORD_FRAME_SIZE = 1280  # 80ms @ 16kHz (openwakeword recommendation)
WAKE_WORD_VAD_THRESHOLD = 0.6


def _quiet_import_onnxruntime():
    """Suppress one-time onnxruntime GPU discovery warning on import."""
    try:
        import os
        import sys
        fd = sys.stderr.fileno()
        old_fd = os.dup(fd)
        with open(os.devnull, 'w') as devnull:
            os.dup2(devnull.fileno(), fd)
            try:
                import onnxruntime  # noqa: F401
            finally:
                os.dup2(old_fd, fd)
                os.close(old_fd)
    except Exception:
        # If onnxruntime isn't available, openwakeword will raise a clearer error later.
        pass

try:
    import pyaudio
except ModuleNotFoundError:  # optional for non-live/test environments
    pyaudio = None

_quiet_import_onnxruntime()

try:
    from openwakeword.model import Model
    import openwakeword.utils as openwakeword_utils
except ModuleNotFoundError:  # optional dependency; required to instantiate
    Model = None
    openwakeword_utils = None


class WakeWordListener(BaseModule):
    def __init__(self, debug: bool = False, verbose: bool = True, event_bus=None):
        super().__init__(__name__, debug=debug, verbose=verbose, event_bus=event_bus)
        if Model is None or openwakeword_utils is None:
            raise RuntimeError(
                "openwakeword is not installed. Install dependencies via `./pi-sat.sh install` "
                "or `pip install openwakeword`."
            )

        openwakeword_utils.download_models()

        self.model = Model(
            wakeword_models=config.WAKE_WORD_MODELS,
            inference_framework=config.INFERENCE_FRAMEWORK,
            vad_threshold=WAKE_WORD_VAD_THRESHOLD,
        )

        self.p = None
        self.stream = None
        self.last_detection_time = 0
        self.cooldown = float(getattr(config, "WAKE_WORD_COOLDOWN", 2.0))
        self.tts_cooldown_end = 0
        self.running = True
        self._heartbeat_counter = 0
        self._last_debug_log = time.time()
        self._debug_log_interval = 0.5
        self._above_threshold_counts = {}
        self._pending_stream_reopen = False
        self._pending_stream_reopen_at = 0.0
        self._audio_queue = queue.Queue(maxsize=50)  # Buffer for callback mode
        if self.event_bus:
            self.event_bus.subscribe(EVENT_RECORDING_FINISHED, self._on_recording_finished)

    def _on_recording_finished(self, event: ControlEvent):
        if self.cooldown <= 0:
            return
        self.tts_cooldown_end = max(self.tts_cooldown_end, time.time() + self.cooldown)
        if self._pending_stream_reopen and self.running:
            self._pending_stream_reopen = False
            self._pending_stream_reopen_at = 0.0
            log_debug(self.logger, "Recreating audio stream after command recording...")
            if not self._recreate_stream():
                self._pending_stream_reopen = True
                self._pending_stream_reopen_at = time.time()

    def _flush_stream_buffer(self):
        """Drop any buffered audio collected while command processing blocked detection."""
        # Clear audio queue (callback mode)
        dropped = 0
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
                dropped += 1
            except queue.Empty:
                break
        if dropped > 0:
            log_debug(self.logger, f"Flushed {dropped} audio frames from queue")

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """Callback for non-blocking audio stream. Puts data in queue."""
        try:
            self._audio_queue.put_nowait(in_data)
        except queue.Full:
            pass  # Drop frame if queue is full
        return (None, pyaudio.paContinue)

    def _recreate_stream(self) -> bool:
        if pyaudio is None:
            return False
        stream_recreated = False
        for retry in range(3):
            try:
                time.sleep(0.1 * (retry + 1))  # Increasing backoff

                if self.p is None:
                    suppress_alsa_errors()
                    suppress_jack_autostart()
                    with suppress_stderr():
                        self.p = pyaudio.PyAudio()

                # Clear audio queue before recreating stream
                while not self._audio_queue.empty():
                    try:
                        self._audio_queue.get_nowait()
                    except queue.Empty:
                        break

                with suppress_stderr():
                    self.stream = self.p.open(
                        format=getattr(pyaudio, config.FORMAT),
                        channels=config.CHANNELS,
                        rate=self._input_rate,
                        input=True,
                        input_device_index=getattr(self, "_input_device_index", None),
                        frames_per_buffer=config.CHUNK,
                        stream_callback=self._audio_callback
                    )
                self.stream.start_stream()

                self._resample_buf = np.zeros(0, dtype=np.int16)

                log_debug(self.logger, "Audio stream recreated successfully")
                stream_recreated = True
                break
            except Exception as stream_error:
                if retry < 2:
                    log_warning(self.logger, f"Stream recreation attempt {retry + 1} failed: {stream_error}, retrying...")
                else:
                    log_error(self.logger, f"Stream recreation failed after 3 attempts: {stream_error}")

        if not stream_recreated:
            log_error(self.logger, "Wake word stream recreation failed; will retry")
        return stream_recreated
        
    def start_listening(self):
        if pyaudio is None:
            raise RuntimeError("pyaudio is not installed; live listening is unavailable")

        if self.p is None:
            suppress_alsa_errors()
            suppress_jack_autostart()
            with suppress_stderr():
                self.p = pyaudio.PyAudio()
        target_rate = int(getattr(config, "RATE", 16000))
        model_rate = 16000
        self._resample_buf = np.zeros(0, dtype=np.int16)
        input_index = find_input_device_index(getattr(config, "INPUT_DEVICE_NAME", None))
        self._input_device_index = input_index if input_index is not None else None
        try:
            with suppress_stderr():
                self.stream = self.p.open(
                    format=getattr(pyaudio, config.FORMAT),
                    channels=config.CHANNELS,
                    rate=target_rate,
                    input=True,
                    input_device_index=self._input_device_index,
                    frames_per_buffer=config.CHUNK,
                    stream_callback=self._audio_callback
                )
            self._input_rate = target_rate
            self.stream.start_stream()
            time.sleep(0.1)
        except Exception as e:
            log_warning(self.logger, f"Failed to open stream at {target_rate}Hz, trying fallback: {e}")
            try:
                with suppress_stderr():
                    if self._input_device_index is not None:
                        info = self.p.get_device_info_by_index(self._input_device_index)
                    else:
                        info = self.p.get_default_input_device_info()
                fallback_rate = int(info.get("defaultSampleRate", 16000))
            except Exception as fallback_err:
                log_warning(self.logger, f"Failed to get default device info: {fallback_err}")
                fallback_rate = 48000
            with suppress_stderr():
                self.stream = self.p.open(
                    format=getattr(pyaudio, config.FORMAT),
                    channels=config.CHANNELS,
                    rate=fallback_rate,
                    input=True,
                    input_device_index=self._input_device_index,
                    frames_per_buffer=config.CHUNK,
                    stream_callback=self._audio_callback
                )
            self._input_rate = fallback_rate
            self.stream.start_stream()
            time.sleep(0.1)
        
        log_info(self.logger, "Wake word listener started...")

        while self.running:
            try:
                self._heartbeat_counter += 1
                if self._heartbeat_counter % 600 == 0:
                    log_debug(self.logger, f"Wake word listener alive (iterations: {self._heartbeat_counter})")

                if self.stream is None:
                    if self._pending_stream_reopen:
                        elapsed = time.time() - self._pending_stream_reopen_at
                        if elapsed >= 0.5:
                            log_debug(self.logger, "Retrying wake word stream recreation...")
                            if self._recreate_stream():
                                self._pending_stream_reopen = False
                                self._pending_stream_reopen_at = 0.0
                            else:
                                self._pending_stream_reopen_at = time.time()
                    time.sleep(0.01)
                    continue

                # Non-blocking read from queue (allows Ctrl+C to work)
                try:
                    data = self._audio_queue.get(timeout=0.5)
                except queue.Empty:
                    continue  # Check self.running and retry

                audio = np.frombuffer(data, dtype=np.int16)

                if getattr(self, "_input_rate", target_rate) != model_rate and audio.size > 0:
                    from scipy.signal import resample_poly
                    from math import gcd
                    g = gcd(model_rate, self._input_rate)
                    up = model_rate // g
                    down = self._input_rate // g
                    resampled = resample_poly(audio.astype(np.float32), up, down)
                    audio = np.clip(resampled, -32768, 32767).astype(np.int16)

                if audio.size > 0:
                    self._resample_buf = np.concatenate((self._resample_buf, audio))
                frame_size = WAKE_WORD_FRAME_SIZE
                while self._resample_buf.size >= frame_size:
                    frame = self._resample_buf[:frame_size]
                    self._resample_buf = self._resample_buf[frame_size:]

                    if self.debug:
                        rms = float(np.sqrt(np.mean(frame.astype(np.float32) ** 2)))

                    try:
                        prediction = self.model.predict(frame)
                    except Exception as pred_error:
                        log_warning(self.logger, f"Model prediction error: {pred_error}")
                        continue
                    current_time = time.time()

                    if self.debug and time.time() - self._last_debug_log >= self._debug_log_interval:
                        confidence_str = ", ".join([f"{ww}: {conf:.3f}" for ww, conf in prediction.items()])
                        log_debug(self.logger, f"🎤 RMS: {rms:>6.1f} | Confidences: {confidence_str}")
                        self._last_debug_log = time.time()

                    for wake_word, confidence in prediction.items():
                        if confidence > config.WAKE_WORD_THRESHOLD:
                            count = self._above_threshold_counts.get(wake_word, 0) + 1
                            self._above_threshold_counts[wake_word] = count
                        else:
                            self._above_threshold_counts[wake_word] = 0
                            continue

                        min_consecutive = int(getattr(config, "WAKE_WORD_MIN_CONSECUTIVE", 1))
                        if count < min_consecutive:
                            continue

                        self._above_threshold_counts[wake_word] = 0
                        if current_time < self.tts_cooldown_end:
                            if self.debug:
                                remaining = self.tts_cooldown_end - current_time
                                log_debug(self.logger, f"🔇 Ignoring detection during TTS cooldown ({remaining:.1f}s remaining)")
                            self._above_threshold_counts[wake_word] = 0
                            continue

                        if current_time - self.last_detection_time >= self.cooldown:
                            self.last_detection_time = current_time
                            log_success(self.logger, f"🔔 WAKE WORD: {wake_word} ({confidence:.2f})")
                            play_wake_sound()
                            try:
                                self.model.reset()
                            except Exception as reset_error:
                                log_warning(self.logger, f"Model reset failed: {reset_error}")
                            if self.event_bus:
                                self.event_bus.publish(
                                    ControlEvent.now(
                                        EVENT_WAKE_WORD_DETECTED,
                                        {
                                            "wake_word": wake_word,
                                            "confidence": round(float(confidence), 3),
                                        },
                                        source="wake_word_listener",
                                    )
                                )

                            log_debug(self.logger, "Closing audio stream for command processing...")
                            if self.stream:
                                self.stream.stop_stream()
                                self.stream.close()
                                self.stream = None
                            if self.event_bus:
                                self._pending_stream_reopen = True
                                self._pending_stream_reopen_at = time.time()
                            else:
                                try:
                                    self._notify_orchestrator()
                                except Exception as notify_error:
                                    log_error(self.logger, f"Command processing error: {notify_error}")
                                log_debug(self.logger, "Recreating audio stream for wake word detection...")
                                if not self._recreate_stream():
                                    self._pending_stream_reopen = True
                                    self._pending_stream_reopen_at = time.time()
                        elif self.debug and confidence > (config.WAKE_WORD_THRESHOLD * 0.5):
                            log_debug(self.logger, f"👂 Low confidence: {wake_word} ({confidence:.2f})")
                
                time.sleep(0.001)
                            
            except KeyboardInterrupt:
                break
            except OSError as e:
                # Stream closed by signal handler - exit cleanly
                if not self.running:
                    break
                log_error(self.logger, f"Wake word listener OS error: {e}")
                time.sleep(0.1)
            except Exception as e:
                if not self.running:
                    break
                log_error(self.logger, f"Wake word listener error: {e}")
                try:
                    self._resample_buf = np.zeros(0, dtype=np.int16)
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
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
        if self.p:
            try:
                self.p.terminate()
            except Exception:
                pass
            self.p = None
        log_info(self.logger, "Wake word listener stopped.")

    def detect_wake_word(self, audio_data):
        if len(audio_data) == 0:
            return False
        
        if audio_data.dtype != np.int16:
            audio_data = (audio_data * 32767).astype(np.int16)
        
        chunk_size = WAKE_WORD_FRAME_SIZE
        detected = False
        
        for i in range(0, len(audio_data), chunk_size):
            chunk = audio_data[i:i+chunk_size]
            if len(chunk) < chunk_size:
                chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
            
            prediction = self.model.predict(chunk)
            
            for wake_word, confidence in prediction.items():
                if confidence > config.WAKE_WORD_THRESHOLD:
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
