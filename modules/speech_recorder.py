import numpy as np
import pyaudio
import config
from .adaptive_silence import AdaptiveSilenceDetector, AdaptiveSilenceConfig
from .base_module import BaseModule
from .logging_utils import log_info, log_success, log_warning, log_error, log_debug, log_audio
from .audio_devices import find_input_device_index
from .audio_normalizer import AudioNormalizer
from .alsa_utils import suppress_alsa_errors, suppress_jack_autostart, suppress_stderr

try:
    import webrtcvad  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    webrtcvad = None


class _FallbackVAD:
    def __init__(self, level: int = 2):  # noqa: ARG002
        pass

    def is_speech(self, frame_bytes: bytes, sample_rate: int) -> bool:  # noqa: ARG002
        return True

class SpeechRecorder(BaseModule):
    def __init__(self, debug: bool = False, verbose: bool = True, event_bus=None):
        super().__init__(__name__, debug=debug, verbose=verbose, event_bus=event_bus)
        self.frame_duration = config.FRAME_DURATION
        self.silence_threshold = config.SILENCE_THRESHOLD
        self.recording_buffer = []
        self.is_recording = False

        if webrtcvad is None:
            log_warning(self.logger, "webrtcvad not installed - falling back to energy-only VAD")
            self.vad = _FallbackVAD(config.VAD_LEVEL)
        else:
            self.vad = webrtcvad.Vad(config.VAD_LEVEL)

        # Audio normalization (handles variable microphone distance)
        self.normalization_enabled = config.AUDIO_NORMALIZATION_ENABLED
        if self.normalization_enabled:
            self.normalizer = AudioNormalizer(
                target_rms=config.AUDIO_TARGET_RMS,
                debug=debug
            )
        else:
            self.normalizer = None

        self._vad_log_counter = 0
        self.adaptive_silence = None
        if getattr(config, "ADAPTIVE_SILENCE_ENABLED", False):
            self.adaptive_silence = AdaptiveSilenceDetector(
                AdaptiveSilenceConfig(
                    ambient_alpha=getattr(config, "ADAPTIVE_AMBIENT_ALPHA", 0.2),
                    silence_ratio=getattr(config, "ADAPTIVE_SILENCE_RATIO", 1.4),
                    min_silence_rms=getattr(config, "ADAPTIVE_MIN_SILENCE_RMS", 300.0),
                )
            )

        suppress_alsa_errors()
        suppress_jack_autostart()
        if debug:
            with suppress_stderr():
                self.p = pyaudio.PyAudio()
        else:
            self.p = None

    def _should_log_vad(self) -> bool:
        self._vad_log_counter += 1
        return self.debug and self._vad_log_counter % 25 == 0

    def _get_input_default_rate(self, p: pyaudio.PyAudio, input_index: int | None, fallback: int) -> int:
        try:
            with suppress_stderr():
                if input_index is not None:
                    info = p.get_device_info_by_index(input_index)
                else:
                    info = p.get_default_input_device_info()
            return int(info.get("defaultSampleRate", fallback))
        except Exception:
            return fallback

    def calibrate_ambient(self, seconds: float = 2.0) -> float:
        if not self.adaptive_silence:
            return 0.0
        if seconds <= 0:
            return 0.0

        import time
        import pyaudio

        suppress_alsa_errors()
        suppress_jack_autostart()
        with suppress_stderr():
            p = pyaudio.PyAudio()

        stream = None
        try:
            input_index = find_input_device_index(getattr(config, "INPUT_DEVICE_NAME", None))
            rate = self._get_input_default_rate(p, input_index, int(getattr(config, "RATE", 48000)))
            chunk = int(rate * (config.FRAME_DURATION / 1000.0))
            with suppress_stderr():
                stream = p.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=rate,
                    input=True,
                    input_device_index=input_index if input_index is not None else None,
                    frames_per_buffer=chunk
                )

            rms_values = []
            end = time.time() + seconds
            while time.time() < end:
                data = stream.read(chunk, exception_on_overflow=False)
                rms = float(np.sqrt(np.mean(np.frombuffer(data, dtype=np.int16).astype(np.float32) ** 2)))
                rms_values.append(rms)

            if not rms_values:
                return 0.0
            ambient = float(np.mean(rms_values))
            self.adaptive_silence.set_ambient(ambient)
            log_info(self.logger, f"Ambient calibrated: {ambient:.1f} RMS")
            return ambient
        finally:
            if stream:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
            try:
                p.terminate()
            except Exception:
                pass
        
    def process_audio_chunks(self, audio, sample_rate: int) -> bytes:
        if sample_rate != 16000:
            raise ValueError("Audio must be 16kHz")
        
        frame_size = int(sample_rate * self.frame_duration / 1000)
        frames = []
        
        for i in range(0, len(audio), frame_size):
            frame = audio[i:i+frame_size]
            if len(frame) == frame_size:
                frames.append(frame)
        
        result, pause_time = self._process_frames_with_pause_detection(frames, sample_rate)
        
        if self.debug:
            if pause_time == -1:
                log_debug(self.logger, f"No pause detected (full recording: {len(result)} bytes)")
            else:
                log_debug(self.logger, f"Pause detected at {pause_time:.2f}s (recording: {len(result)} bytes)")
        
        if self.debug and result:
            self._playback_audio(result, sample_rate)
        
        return result
    
    def _process_frames_with_pause_detection(self, frames, sample_rate):
        speech_frames = []
        silence_count = 0
        silence_threshold_frames = int(sample_rate * self.silence_threshold / (sample_rate * self.frame_duration / 1000))
        pause_time = -1
        
        for i, frame in enumerate(frames):
            frame_bytes = frame.tobytes()
            
            try:
                is_speech = self.vad.is_speech(frame_bytes, sample_rate)
            except (ValueError, TypeError, Exception) as e:
                if self.debug:
                    log_debug(self.logger, f"VAD error: {e}")
                is_speech = False
            
            if is_speech:
                speech_frames.append(frame)
                silence_count = 0
            else:
                silence_count += 1
                if silence_count <= silence_threshold_frames:
                    speech_frames.append(frame)
                else:
                    pause_time = (i * self.frame_duration) / 1000.0
                    break
        
        if not speech_frames:
            return b"", -1
        
        return np.concatenate(speech_frames).tobytes(), pause_time
    
    def _process_frames(self, frames):
        speech_frames = []
        silence_count = 0
        
        for frame in frames:
            frame_bytes = frame.tobytes()
            
            try:
                is_speech = self.vad.is_speech(frame_bytes, 16000)
            except (ValueError, TypeError, Exception) as e:
                is_speech = False
            
            if is_speech:
                speech_frames.append(frame)
                silence_count = 0
            else:
                silence_count += 1
                if silence_count <= 10:
                    speech_frames.append(frame)
        
        if not speech_frames:
            return b""
        
        return np.concatenate(speech_frames).tobytes()
    
    def _playback_audio(self, audio_bytes, sample_rate):
        if not self.debug or not self.p:
            return
            
        audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
        
        stream = self.p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=sample_rate,
            output=True
        )
        
        try:
            stream.write(audio_bytes)
            log_audio(self.logger, f"Played back {len(audio_bytes)} bytes")
        finally:
            stream.stop_stream()
            stream.close()
    
    def start_recording(self) -> None:
        self.recording_buffer = []
        self.is_recording = True

    def stop_recording(self) -> bytes:
        self.is_recording = False
        if self.recording_buffer:
            result = np.concatenate(self.recording_buffer).tobytes()
            if self.debug and result:
                self._playback_audio(result, 16000)
            return result
        return b""
    
    def process_frame(self, frame):
        if not self.is_recording:
            return
        
        frame_bytes = frame.tobytes()
        
        try:
            is_speech = self.vad.is_speech(frame_bytes, 16000)
        except (ValueError, TypeError, Exception) as e:
            # Invalid frame or VAD error - treat as non-speech
            is_speech = False
        
        if is_speech:
            self.recording_buffer.append(frame)
    

    def record_command(self):
        if self.debug and config.DEBUG_DUMMY_AUDIO:
            import math
            sample_rate = config.SAMPLE_RATE
            duration = 2.0
            frequency = 440
            samples = int(sample_rate * duration)
            
            t = np.linspace(0, duration, samples)
            audio = np.sin(2 * np.pi * frequency * t) * 0.3
            audio += np.sin(2 * np.pi * frequency * 1.5 * t) * 0.1
            
            audio = (audio * 32767).astype(np.int16)
            return audio.tobytes()
        
        import pyaudio
        import time

        p = None
        stream = None
        frames = []

        try:
            format = pyaudio.paInt16
            channels = config.CHANNELS
            silence_threshold = config.SILENCE_THRESHOLD
            target_rate = config.SAMPLE_RATE

            frame_duration = config.FRAME_DURATION / 1000.0

            suppress_alsa_errors()
            suppress_jack_autostart()
            with suppress_stderr():
                p = pyaudio.PyAudio()
            input_index = find_input_device_index(getattr(config, "INPUT_DEVICE_NAME", None))

            rate = target_rate
            chunk = int(rate * frame_duration)
            try:
                with suppress_stderr():
                    stream = p.open(
                        format=format,
                        channels=channels,
                        rate=rate,
                        input=True,
                        input_device_index=input_index if input_index is not None else None,
                        frames_per_buffer=chunk
                    )
            except Exception as e:
                if self.debug:
                    log_debug(self.logger, f"Primary input open failed (index={input_index}, rate={rate}): {e}")
                rate = self._get_input_default_rate(p, input_index, config.RATE)
                chunk = int(rate * frame_duration)
                try:
                    with suppress_stderr():
                        stream = p.open(
                            format=format,
                            channels=channels,
                            rate=rate,
                            input=True,
                            input_device_index=input_index if input_index is not None else None,
                            frames_per_buffer=chunk
                        )
                except Exception as fallback_error:
                    if self.debug:
                        log_debug(self.logger, f"Fallback input open failed (index={input_index}, rate={rate}): {fallback_error}")
                    # Last resort: use default input device (PipeWire/Pulse default)
                    with suppress_stderr():
                        stream = p.open(
                            format=format,
                            channels=channels,
                            rate=rate,
                            input=True,
                            input_device_index=None,
                            frames_per_buffer=chunk
                        )

            silence_count = 0
            speech_detected = False
            silence_frames = int(silence_threshold / frame_duration)
            min_recording_time = 1.5
            max_recording_time = config.MAX_RECORDING_TIME
            start_time = time.time()

            vad_rate = 16000
            frame_size_16k = int(vad_rate * frame_duration)

            log_audio(self.logger, "🎤 Recording (immediate start)...")

            while True:
                data = stream.read(chunk, exception_on_overflow=False)
                frames.append(data)

                if rate != vad_rate:
                    from scipy.signal import resample_poly
                    from math import gcd
                    audio_48k = np.frombuffer(data, dtype=np.int16)
                    g = gcd(vad_rate, rate)
                    up = vad_rate // g
                    down = rate // g
                    audio_16k = resample_poly(audio_48k.astype(np.float32), up, down)
                    audio_16k = np.clip(audio_16k, -32768, 32767).astype(np.int16)

                    if len(audio_16k) < frame_size_16k:
                        audio_16k = np.pad(audio_16k, (0, frame_size_16k - len(audio_16k)))
                    elif len(audio_16k) > frame_size_16k:
                        audio_16k = audio_16k[:frame_size_16k]

                    vad_data = audio_16k.tobytes()
                else:
                    vad_data = data

                try:
                    is_speech = self.vad.is_speech(vad_data, vad_rate)
                except (ValueError, TypeError) as e:
                    if self.debug:
                        log_debug(self.logger, f"VAD error: {e}")
                    is_speech = False
                except Exception as e:
                    log_warning(self.logger, f"Unexpected VAD error: {e}")
                    is_speech = False
                if self.adaptive_silence:
                    rms = float(np.sqrt(np.mean(np.frombuffer(vad_data, dtype=np.int16).astype(np.float32) ** 2)))
                    is_speech, threshold = self.adaptive_silence.update(rms, is_speech)
                    if self._should_log_vad():
                        log_debug(
                            self.logger,
                            f"Adaptive silence: rms={rms:.1f} threshold={threshold:.1f} speech={is_speech}"
                        )

                if is_speech:
                    if not speech_detected:
                        speech_detected = True
                        log_audio(self.logger, "🗣️  Speech detected")
                    silence_count = 0
                else:
                    silence_count += 1

                elapsed_time = time.time() - start_time
                if self._should_log_vad():
                    log_debug(
                        self.logger,
                        f"Silence count: {silence_count}/{silence_frames} (elapsed={elapsed_time:.1f}s)"
                    )

                if elapsed_time >= min_recording_time and speech_detected and silence_count >= silence_frames:
                    log_audio(self.logger, f"🎤 Recording complete: {elapsed_time:.1f}s ({len(frames)} frames)")
                    break

                if elapsed_time >= max_recording_time:
                    log_audio(self.logger, f"🎤 Max time reached ({max_recording_time}s, {len(frames)} frames)")
                    break

        except KeyboardInterrupt:
            log_warning(self.logger, "🎤 Recording interrupted")
        except Exception as e:
            log_error(self.logger, f"Recording error: {e}")
        finally:
            if stream:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception as e:
                    log_warning(self.logger, f"Error closing stream: {e}")
            if p:
                try:
                    p.terminate()
                except Exception as e:
                    log_warning(self.logger, f"Error terminating PyAudio: {e}")

        if not frames:
            return b""

        raw_audio = b''.join(frames)

        audio_rate = rate
        if rate != target_rate and raw_audio:
            audio_array = np.frombuffer(raw_audio, dtype=np.int16).astype(np.float32)
            if audio_array.size > 0:
                ratio = target_rate / float(rate)
                new_len = max(1, int(round(audio_array.size * ratio)))
                x_old = np.linspace(0.0, 1.0, num=audio_array.size, dtype=np.float32)
                x_new = np.linspace(0.0, 1.0, num=new_len, dtype=np.float32)
                resampled = np.interp(x_new, x_old, audio_array)
                raw_audio = np.clip(resampled, -32768, 32767).astype(np.int16).tobytes()
                audio_rate = target_rate

        audio_data = raw_audio

        if self.debug:
            duration = len(audio_data) / (audio_rate * 2)  # 2 bytes per sample (int16)
            log_debug(self.logger, f"Raw audio: {len(audio_data)} bytes = {duration:.2f}s at {audio_rate}Hz")

        if self.normalization_enabled and self.normalizer and audio_data:
            audio_data = self.normalizer.normalize_audio(audio_data)
            if self.debug:
                duration_normalized = len(audio_data) / (audio_rate * 2)
                log_debug(self.logger, f"After normalization: {len(audio_data)} bytes = {duration_normalized:.2f}s")

        return audio_data

    def _trim_silence(self, audio_bytes: bytes, sample_rate: int) -> bytes:
        if not audio_bytes:
            return b""

        audio_array = np.frombuffer(audio_bytes, dtype=np.int16)

        frame_duration_ms = config.FRAME_DURATION
        frame_size = int(sample_rate * frame_duration_ms / 1000)
        vad_rate = 16000
        vad_frame_size = int(vad_rate * frame_duration_ms / 1000)

        first_speech = None
        last_speech = None

        for i in range(0, len(audio_array), frame_size):
            frame = audio_array[i:i+frame_size]
            if len(frame) < frame_size:
                frame = np.pad(frame, (0, frame_size - len(frame)))

            if sample_rate != vad_rate:
                ratio = vad_rate / float(sample_rate)
                new_len = int(len(frame) * ratio)
                x_old = np.linspace(0, 1, len(frame), dtype=np.float32)
                x_new = np.linspace(0, 1, new_len, dtype=np.float32)
                frame_16k = np.interp(x_new, x_old, frame.astype(np.float32))
                frame_16k = np.clip(frame_16k, -32768, 32767).astype(np.int16)

                if len(frame_16k) < vad_frame_size:
                    frame_16k = np.pad(frame_16k, (0, vad_frame_size - len(frame_16k)))
                elif len(frame_16k) > vad_frame_size:
                    frame_16k = frame_16k[:vad_frame_size]

                vad_frame = frame_16k.tobytes()
            else:
                vad_frame = frame.tobytes()

            try:
                is_speech = self.vad.is_speech(vad_frame, vad_rate)
            except (ValueError, TypeError) as e:
                if self.debug:
                    log_debug(self.logger, f"VAD error in trim: {e}")
                is_speech = False

            if is_speech:
                if first_speech is None:
                    first_speech = i
                last_speech = i + frame_size

        if first_speech is None:
            if self.debug:
                log_debug(self.logger, "No speech detected in post-processing trim - returning full recording")
            return audio_bytes

        padding_before = int(sample_rate * 0.3)
        padding_after = int(sample_rate * 0.2)
        first_speech = max(0, first_speech - padding_before)
        last_speech = min(len(audio_array), last_speech + padding_after)

        trimmed = audio_array[first_speech:last_speech]

        if self.debug:
            original_duration = len(audio_array) / sample_rate
            trimmed_duration = len(trimmed) / sample_rate
            log_debug(self.logger, f"Trimmed: {original_duration:.2f}s → {trimmed_duration:.2f}s")

        return trimmed.tobytes()

    def __del__(self):
        if self.p:
            self.p.terminate()
