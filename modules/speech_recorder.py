import numpy as np
import pyaudio
import config
from .logging_utils import setup_logger, log_info, log_success, log_warning, log_error, log_debug, log_audio
from .audio_devices import find_input_device_index
from .audio_normalizer import AudioNormalizer

try:
    import webrtcvad  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    webrtcvad = None


class _FallbackVAD:
    """Fallback when webrtcvad is unavailable (energy-only path can still work)."""

    def __init__(self, level: int = 2):  # noqa: ARG002
        pass

    def is_speech(self, frame_bytes: bytes, sample_rate: int) -> bool:  # noqa: ARG002
        # Let the energy-based detector decide.
        return True

class SpeechRecorder:
    def __init__(self, debug=False):
        self.frame_duration = config.FRAME_DURATION
        self.silence_threshold = config.SILENCE_THRESHOLD
        self.recording_buffer = []
        self.is_recording = False
        self.debug = debug
        self.logger = setup_logger(__name__, debug=debug)

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

        self.p = pyaudio.PyAudio() if debug else None
        
    def process_audio_chunks(self, audio, sample_rate: int) -> bytes:
        """Process audio chunks with VAD and pause detection."""
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
                # Invalid frame size/rate or VAD error - treat as non-speech
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
                # Invalid frame or VAD error - treat as non-speech
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
        """Start recording audio frames."""
        self.recording_buffer = []
        self.is_recording = True

    def stop_recording(self) -> bytes:
        """Stop recording and return recorded audio."""
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
        """
        Record voice command with immediate start and post-processing VAD.

        Strategy:
        - Records immediately (no calibration delay)
        - Captures audio until silence detected or max duration
        - Post-processes to trim silence from beginning/end
        - Returns clean speech audio
        """
        if self.debug and config.DEBUG_DUMMY_AUDIO:
            # Return a dummy audio buffer with some speech-like content for testing
            # Create a simple sine wave to simulate speech
            import math
            sample_rate = config.SAMPLE_RATE
            duration = 2.0  # 2 seconds
            frequency = 440  # A4 note
            samples = int(sample_rate * duration)
            
            # Generate a sine wave with some variation to simulate speech
            t = np.linspace(0, duration, samples)
            audio = np.sin(2 * np.pi * frequency * t) * 0.3
            audio += np.sin(2 * np.pi * frequency * 1.5 * t) * 0.1  # Add harmonics
            
            # Convert to int16
            audio = (audio * 32767).astype(np.int16)
            return audio.tobytes()
        
        import pyaudio
        import time

        # Initialize to None for safe cleanup
        p = None
        stream = None
        frames = []

        try:
            # Audio settings
            format = pyaudio.paInt16
            channels = config.CHANNELS
            silence_threshold = config.SILENCE_THRESHOLD
            target_rate = config.SAMPLE_RATE  # Hailo Whisper expects 16kHz mono

            # Use frame_duration-sized chunks so VAD timing matches real audio duration
            frame_duration = config.FRAME_DURATION / 1000.0  # seconds

            p = pyaudio.PyAudio()
            input_index = find_input_device_index(getattr(config, "INPUT_DEVICE_NAME", None))

            # Prefer 16kHz capture for direct STT input; fallback to device default if unsupported
            rate = target_rate
            chunk = int(rate * frame_duration)
            try:
                stream = p.open(
                    format=format,
                    channels=channels,
                    rate=rate,
                    input=True,
                    input_device_index=input_index if input_index is not None else None,
                    frames_per_buffer=chunk
                )
            except Exception:
                try:
                    info = p.get_default_input_device_info()
                    rate = int(info.get("defaultSampleRate", config.RATE))
                except Exception:
                    rate = config.RATE
                chunk = int(rate * frame_duration)
                stream = p.open(
                    format=format,
                    channels=channels,
                    rate=rate,
                    input=True,
                    input_device_index=input_index if input_index is not None else None,
                    frames_per_buffer=chunk
                )

            silence_count = 0
            speech_detected = False
            silence_frames = int(silence_threshold / frame_duration)
            min_recording_time = 1.5  # Minimum 1.5s to give user time to speak
            max_recording_time = config.MAX_RECORDING_TIME
            start_time = time.time()

            # For VAD: need 16kHz frames
            vad_rate = 16000
            frame_size_16k = int(vad_rate * frame_duration)

            log_audio(self.logger, "🎤 Recording (immediate start)...")

            while True:
                data = stream.read(chunk, exception_on_overflow=False)
                frames.append(data)

                # Resample to 16kHz for VAD if needed
                if rate != vad_rate:
                    audio_48k = np.frombuffer(data, dtype=np.int16)
                    # Simple linear interpolation to 16kHz
                    ratio = vad_rate / float(rate)
                    new_len = int(len(audio_48k) * ratio)
                    x_old = np.linspace(0, 1, len(audio_48k), dtype=np.float32)
                    x_new = np.linspace(0, 1, new_len, dtype=np.float32)
                    audio_16k = np.interp(x_new, x_old, audio_48k.astype(np.float32))
                    audio_16k = np.clip(audio_16k, -32768, 32767).astype(np.int16)

                    # Ensure exact frame size for VAD
                    if len(audio_16k) < frame_size_16k:
                        audio_16k = np.pad(audio_16k, (0, frame_size_16k - len(audio_16k)))
                    elif len(audio_16k) > frame_size_16k:
                        audio_16k = audio_16k[:frame_size_16k]

                    vad_data = audio_16k.tobytes()
                else:
                    vad_data = data

                # Check for silence using VAD (16kHz data)
                try:
                    is_speech = self.vad.is_speech(vad_data, vad_rate)
                except (ValueError, TypeError) as e:
                    # Invalid frame or VAD error - treat as non-speech
                    if self.debug:
                        log_debug(self.logger, f"VAD error: {e}")
                    is_speech = False
                except Exception as e:
                    # Unexpected VAD error - log always (not just in debug)
                    log_warning(self.logger, f"Unexpected VAD error: {e}")
                    is_speech = False

                if is_speech:
                    if not speech_detected:
                        speech_detected = True
                        log_audio(self.logger, "🗣️  Speech detected")
                    silence_count = 0
                else:
                    silence_count += 1

                # Stop conditions
                elapsed_time = time.time() - start_time

                # Only stop on silence after minimum recording time
                if elapsed_time >= min_recording_time and speech_detected and silence_count >= silence_frames:
                    log_audio(self.logger, f"🎤 Recording complete: {elapsed_time:.1f}s ({len(frames)} frames)")
                    break

                # Hard stop at max recording time
                if elapsed_time >= max_recording_time:
                    log_audio(self.logger, f"🎤 Max time reached ({max_recording_time}s, {len(frames)} frames)")
                    break

        except KeyboardInterrupt:
            log_warning(self.logger, "🎤 Recording interrupted")
        except Exception as e:
            log_error(self.logger, f"Recording error: {e}")
        finally:
            # Safe cleanup - check existence before closing
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

        # Join all frames
        raw_audio = b''.join(frames)

        # Ensure 16kHz mono int16 for Hailo Whisper
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

        # TEMPORARY: Skip trimming - return full recording
        # The VAD-based trimming might be too aggressive
        # Post-process: trim silence from beginning and end
        # audio_data = self._trim_silence(raw_audio, rate)
        audio_data = raw_audio

        if self.debug:
            duration = len(audio_data) / (audio_rate * 2)  # 2 bytes per sample (int16)
            log_debug(self.logger, f"Raw audio: {len(audio_data)} bytes = {duration:.2f}s at {audio_rate}Hz")

        # Apply audio normalization if enabled
        if self.normalization_enabled and self.normalizer and audio_data:
            audio_data = self.normalizer.normalize_audio(audio_data)
            if self.debug:
                duration_normalized = len(audio_data) / (audio_rate * 2)
                log_debug(self.logger, f"After normalization: {len(audio_data)} bytes = {duration_normalized:.2f}s")

        return audio_data

    def _trim_silence(self, audio_bytes: bytes, sample_rate: int) -> bytes:
        """
        Trim silence from beginning and end of recording using post-processing VAD.

        Args:
            audio_bytes: Raw audio data
            sample_rate: Sample rate (Hz)

        Returns:
            Trimmed audio data
        """
        if not audio_bytes:
            return b""

        # Convert to numpy array for processing
        audio_array = np.frombuffer(audio_bytes, dtype=np.int16)

        # Process in VAD-compatible frames (VAD requires 16kHz)
        frame_duration_ms = config.FRAME_DURATION
        frame_size = int(sample_rate * frame_duration_ms / 1000)
        vad_rate = 16000
        vad_frame_size = int(vad_rate * frame_duration_ms / 1000)

        # Find first and last speech frames
        first_speech = None
        last_speech = None

        for i in range(0, len(audio_array), frame_size):
            frame = audio_array[i:i+frame_size]
            if len(frame) < frame_size:
                # Pad last frame if needed
                frame = np.pad(frame, (0, frame_size - len(frame)))

            # Resample to 16kHz for VAD if needed
            if sample_rate != vad_rate:
                ratio = vad_rate / float(sample_rate)
                new_len = int(len(frame) * ratio)
                x_old = np.linspace(0, 1, len(frame), dtype=np.float32)
                x_new = np.linspace(0, 1, new_len, dtype=np.float32)
                frame_16k = np.interp(x_new, x_old, frame.astype(np.float32))
                frame_16k = np.clip(frame_16k, -32768, 32767).astype(np.int16)

                # Ensure exact frame size
                if len(frame_16k) < vad_frame_size:
                    frame_16k = np.pad(frame_16k, (0, vad_frame_size - len(frame_16k)))
                elif len(frame_16k) > vad_frame_size:
                    frame_16k = frame_16k[:vad_frame_size]

                vad_frame = frame_16k.tobytes()
            else:
                vad_frame = frame.tobytes()

            try:
                is_speech = self.vad.is_speech(vad_frame, vad_rate)
            except:
                is_speech = False

            if is_speech:
                if first_speech is None:
                    first_speech = i
                last_speech = i + frame_size

        # If no speech found, return original audio (VAD might have failed)
        if first_speech is None:
            if self.debug:
                log_debug(self.logger, "No speech detected in post-processing trim - returning full recording")
            return audio_bytes

        # Add generous padding around speech (300ms before, 200ms after)
        padding_before = int(sample_rate * 0.3)
        padding_after = int(sample_rate * 0.2)
        first_speech = max(0, first_speech - padding_before)
        last_speech = min(len(audio_array), last_speech + padding_after)

        # Trim and return
        trimmed = audio_array[first_speech:last_speech]

        if self.debug:
            original_duration = len(audio_array) / sample_rate
            trimmed_duration = len(trimmed) / sample_rate
            log_debug(self.logger, f"Trimmed: {original_duration:.2f}s → {trimmed_duration:.2f}s")

        return trimmed.tobytes()

    def __del__(self):
        if self.p:
            self.p.terminate()

if __name__ == "__main__":
    recorder = SpeechRecorder(debug=True)
    log_info(recorder.logger, "Speech recorder module loaded with debug mode") 
