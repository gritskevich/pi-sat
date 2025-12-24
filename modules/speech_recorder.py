import numpy as np
import pyaudio
import config
from .logging_utils import setup_logger, log_info, log_success, log_warning, log_error, log_debug, log_audio
from .audio_devices import find_input_device_index

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
    
    def record_from_stream(self, stream, input_rate=48000, max_duration=10.0, skip_initial_seconds=0.0):
        """
        Record from existing stream with adaptive silence detection.

        Uses energy-based VAD with adaptive threshold:
        - Measures ambient noise level during calibration phase
        - Detects speech based on energy relative to noise floor
        - Smart end-of-speech detection with trailing silence

        Args:
            stream: Open PyAudio stream
            input_rate: Stream sample rate (default: 48000)
            max_duration: Maximum recording duration in seconds
            skip_initial_seconds: Discard this many seconds at start (e.g., 0.7 for wake sound)
                                  Allows recording to start immediately without blocking delay

        Returns:
            Audio data as 16 kHz mono int16 PCM bytes (raw, no WAV header)
        """
        import time

        frame_duration_ms = int(config.FRAME_DURATION)
        frame_duration_s = frame_duration_ms / 1000.0
        frames_per_second = 1.0 / frame_duration_s

        # Work in fixed-size frames so WebRTC VAD receives valid 10/20/30ms chunks.
        in_frame_samples = max(1, int(round(float(input_rate) * frame_duration_s)))
        out_rate = 16000
        out_frame_samples = max(1, int(round(float(out_rate) * frame_duration_s)))

        # Adaptive parameters from config
        speech_threshold_multiplier = float(config.VAD_SPEECH_MULTIPLIER)
        silence_frames_threshold = int(float(config.VAD_SILENCE_DURATION) * frames_per_second)
        min_speech_frames = int(float(config.VAD_MIN_SPEECH_DURATION) * frames_per_second)

        # Skip frames at the start (wake sound contamination)
        skip_frames = int(round(float(skip_initial_seconds) * frames_per_second)) if skip_initial_seconds > 0 else 0
        frames_skipped = 0

        # Calibration phase (after skip): measure noise floor for ~0.3s
        calibration_frames = max(1, int(round(0.3 * frames_per_second)))
        calibration_energy: list[float] = []
        noise_floor = 0.0
        speech_threshold = 0.0

        # Pre-roll to avoid clipping the start of speech
        pre_roll_max = max(1, calibration_frames)
        pre_roll_frames: list[bytes] = []

        input_buf = np.zeros(0, dtype=np.int16)
        output_frames: list[bytes] = []
        speech_started = False
        speech_frame_count = 0
        silence_frames = 0

        processed_frames_total = 0
        max_frames_total = int(round(float(max_duration) * frames_per_second))
        max_reached = False

        if skip_initial_seconds > 0:
            log_audio(self.logger, f"🎤 Recording (skip {skip_initial_seconds:.2f}s, frame {frame_duration_ms}ms)...")
        else:
            log_audio(self.logger, f"🎤 Recording (frame {frame_duration_ms}ms)...")

        def _resample_frame_to_16k(frame_in: np.ndarray) -> np.ndarray:
            if input_rate == out_rate:
                if frame_in.size == out_frame_samples:
                    return frame_in
                # Pad/truncate defensively if rates match but rounding differs.
                if frame_in.size > out_frame_samples:
                    return frame_in[:out_frame_samples]
                pad = np.zeros(out_frame_samples - frame_in.size, dtype=np.int16)
                return np.concatenate([frame_in, pad])

            src = frame_in.astype(np.float32)
            x_old = np.linspace(0.0, 1.0, num=src.size, dtype=np.float32)
            x_new = np.linspace(0.0, 1.0, num=out_frame_samples, dtype=np.float32)
            resampled = np.interp(x_new, x_old, src)
            return np.clip(resampled, -32768, 32767).astype(np.int16)

        while True:
            try:
                data = stream.read(config.CHUNK, exception_on_overflow=False)
            except Exception as e:
                log_error(self.logger, f"Recording error (stream.read): {e}")
                break

            audio_in = np.frombuffer(data, dtype=np.int16)
            if audio_in.size == 0:
                continue

            input_buf = np.concatenate((input_buf, audio_in))

            while input_buf.size >= in_frame_samples:
                frame_in = input_buf[:in_frame_samples]
                input_buf = input_buf[in_frame_samples:]

                if frames_skipped < skip_frames:
                    frames_skipped += 1
                    processed_frames_total += 1
                    if max_frames_total > 0 and processed_frames_total >= max_frames_total:
                        max_reached = True
                        break
                    continue

                processed_frames_total += 1
                if max_frames_total > 0 and processed_frames_total >= max_frames_total:
                    max_reached = True

                frame_16k = _resample_frame_to_16k(frame_in)
                energy = float(np.sqrt(np.mean(frame_16k.astype(np.float32) ** 2)))

                # Calibration (keep frames in pre-roll, don't drop audio)
                if len(calibration_energy) < calibration_frames:
                    calibration_energy.append(energy)
                    pre_roll_frames.append(frame_16k.tobytes())
                    if len(pre_roll_frames) > pre_roll_max:
                        pre_roll_frames.pop(0)

                    if len(calibration_energy) == calibration_frames:
                        noise_floor = float(np.median(calibration_energy))
                        if noise_floor < 1.0:
                            noise_floor = 1.0
                        speech_threshold = noise_floor * speech_threshold_multiplier
                        log_audio(
                            self.logger,
                            f"📊 Noise floor: {noise_floor:.1f} RMS → Speech threshold: {speech_threshold:.1f} RMS ({speech_threshold_multiplier}x)",
                        )
                    continue

                # WebRTC VAD (16k, 10/20/30ms frames only)
                try:
                    is_speech_vad = self.vad.is_speech(frame_16k.tobytes(), out_rate)
                except (ValueError, TypeError, Exception) as e:
                    # Invalid frame size/rate or VAD error - treat as non-speech
                    is_speech_vad = False

                is_speech_energy = energy > speech_threshold
                is_speech = is_speech_vad and is_speech_energy

                if self.debug and (speech_started or is_speech):
                    log_debug(
                        self.logger,
                        f"Energy: {energy:.1f}, Thresh: {speech_threshold:.1f}, VAD: {is_speech_vad}, EnergyOK: {is_speech_energy}, Speech: {is_speech}",
                    )

                if not speech_started:
                    # Maintain rolling pre-roll until speech starts.
                    pre_roll_frames.append(frame_16k.tobytes())
                    if len(pre_roll_frames) > pre_roll_max:
                        pre_roll_frames.pop(0)

                if is_speech:
                    if not speech_started:
                        speech_started = True
                        output_frames.extend(pre_roll_frames)
                        pre_roll_frames.clear()
                        log_audio(self.logger, f"🗣️  Speech detected (energy: {energy:.1f} > {speech_threshold:.1f})")
                    output_frames.append(frame_16k.tobytes())
                    speech_frame_count += 1
                    silence_frames = 0
                else:
                    if speech_started:
                        output_frames.append(frame_16k.tobytes())
                        silence_frames += 1

                # End detection - enough silence after minimum speech
                if speech_started and silence_frames >= silence_frames_threshold and speech_frame_count >= min_speech_frames:
                    recorded_s = processed_frames_total * frame_duration_s
                    log_audio(self.logger, f"Recording complete: {recorded_s:.1f}s")
                    return b"".join(output_frames)

                if max_reached:
                    break

            if max_reached:
                recorded_s = processed_frames_total * frame_duration_s
                log_audio(self.logger, f"🎤 Max recording time reached ({recorded_s:.1f}s)")
                break

        if not speech_started:
            return b""

        return b"".join(output_frames)

    def record_command(self):
        """Record a command using microphone input with VAD"""
        if self.debug:
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
        
        # Audio settings
        chunk = config.CHUNK
        format = pyaudio.paInt16
        channels = config.CHANNELS
        rate = config.RATE
        silence_threshold = config.SILENCE_THRESHOLD
        
        p = pyaudio.PyAudio()
        input_index = find_input_device_index(getattr(config, "INPUT_DEVICE_NAME", None))
        stream = p.open(
            format=format,
            channels=channels,
            rate=rate,
            input=True,
            input_device_index=input_index if input_index is not None else None,
            frames_per_buffer=chunk
        )
        
        frames = []
        silence_count = 0
        frame_duration = config.FRAME_DURATION / 1000.0  # Convert to seconds
        silence_frames = int(silence_threshold / frame_duration)
        min_recording_time = 2.0  # Minimum 2 seconds recording
        max_recording_time = config.MAX_RECORDING_TIME  # Maximum recording time
        start_time = time.time()
        
        log_audio(self.logger, "🎤 Starting microphone recording...")
        
        try:
            while True:
                data = stream.read(chunk)
                frames.append(data)
                
                # Check for silence using VAD
                try:
                    is_speech = self.vad.is_speech(data, rate)
                except (ValueError, TypeError, Exception) as e:
                    # Invalid frame or VAD error - treat as non-speech
                    is_speech = False
                
                if is_speech:
                    silence_count = 0
                else:
                    silence_count += 1
                
                # Only stop if we've recorded minimum time AND detected enough silence
                elapsed_time = time.time() - start_time
                if elapsed_time >= min_recording_time and silence_count >= silence_frames:
                    break
                
                # Also stop if we've reached maximum recording time
                if elapsed_time >= max_recording_time:
                    log_audio(self.logger, f"🎤 Maximum recording time reached ({max_recording_time}s)")
                    break
            
            log_audio(self.logger, f"🎤 Recording complete: {len(frames)} frames ({elapsed_time:.1f}s)")
            
        except KeyboardInterrupt:
            log_warning(self.logger, "🎤 Recording interrupted")
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()
        
        if frames:
            return b''.join(frames)
        else:
            return b""
    
    def __del__(self):
        if self.p:
            self.p.terminate()

if __name__ == "__main__":
    recorder = SpeechRecorder(debug=True)
    log_info(recorder.logger, "Speech recorder module loaded with debug mode") 
