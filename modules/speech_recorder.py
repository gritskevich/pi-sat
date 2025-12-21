import numpy as np
import webrtcvad
import pyaudio
import config
from .logging_utils import setup_logger, log_info, log_success, log_warning, log_error, log_debug, log_audio
from .audio_devices import find_input_device_index

class SpeechRecorder:
    def __init__(self, debug=False):
        self.vad = webrtcvad.Vad(config.VAD_LEVEL)
        self.frame_duration = config.FRAME_DURATION
        self.silence_threshold = config.SILENCE_THRESHOLD
        self.recording_buffer = []
        self.is_recording = False
        self.debug = debug
        self.p = pyaudio.PyAudio() if debug else None
        self.logger = setup_logger(__name__, debug=debug)
        
    def process_audio_chunks(self, audio, sample_rate):
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
            except:
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
            except:
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
    
    def start_recording(self):
        self.recording_buffer = []
        self.is_recording = True
    
    def stop_recording(self):
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
        except:
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
            Audio data as bytes
        """
        import time

        frames = []
        speech_started = False
        silence_frames = 0

        # Adaptive parameters from config
        noise_floor = 0
        speech_threshold_multiplier = config.VAD_SPEECH_MULTIPLIER
        silence_duration = config.VAD_SILENCE_DURATION
        min_speech_duration = config.VAD_MIN_SPEECH_DURATION

        frame_duration_ms = config.FRAME_DURATION
        frames_per_second = 1000 / frame_duration_ms
        silence_frames_threshold = int(silence_duration * frames_per_second)
        min_speech_frames = int(min_speech_duration * frames_per_second)

        start_time = time.time()
        speech_frame_count = 0

        # Skip initial frames (e.g., wake sound contamination)
        skip_frames = int(skip_initial_seconds * frames_per_second) if skip_initial_seconds > 0 else 0
        frames_skipped = 0

        # Calibration phase - measure noise floor (first 0.3s AFTER skipped frames)
        calibration_frames = int(0.3 * frames_per_second)
        calibration_energy = []

        if skip_initial_seconds > 0:
            log_audio(self.logger, f"🎤 Recording with adaptive VAD (skipping first {skip_initial_seconds:.1f}s)...")
        else:
            log_audio(self.logger, "🎤 Recording with adaptive VAD...")

        while True:
            elapsed = time.time() - start_time
            if elapsed > max_duration:
                log_audio(self.logger, f"🎤 Max recording time reached ({max_duration}s)")
                break

            try:
                data = stream.read(config.CHUNK, exception_on_overflow=False)
                audio = np.frombuffer(data, dtype=np.int16)

                # Skip initial frames (wake sound contamination)
                if frames_skipped < skip_frames:
                    frames_skipped += 1
                    if self.debug and frames_skipped % 10 == 0:
                        log_debug(self.logger, f"Skipping frames: {frames_skipped}/{skip_frames}")
                    continue  # Discard frame without processing

                # Resample to 16kHz for VAD if needed
                if input_rate != 16000 and audio.size > 0:
                    src = audio.astype(np.float32)
                    ratio = 16000 / float(input_rate)
                    new_len = max(1, int(round(audio.size * ratio)))
                    x_old = np.linspace(0.0, 1.0, num=audio.size, dtype=np.float32)
                    x_new = np.linspace(0.0, 1.0, num=new_len, dtype=np.float32)
                    resampled = np.interp(x_new, x_old, src)
                    audio_16k = np.clip(resampled, -32768, 32767).astype(np.int16)
                else:
                    audio_16k = audio

                # Calculate energy (RMS)
                energy = np.sqrt(np.mean(audio_16k.astype(np.float32) ** 2))

                # Calibration phase - measure ambient noise (AFTER skipped frames)
                if len(calibration_energy) < calibration_frames:
                    calibration_energy.append(energy)
                    if self.debug and len(calibration_energy) % 5 == 0:
                        log_debug(self.logger, f"Calibrating... ({len(calibration_energy)}/{calibration_frames} frames, current energy: {energy:.1f})")
                    if len(calibration_energy) == calibration_frames:
                        noise_floor = np.median(calibration_energy)
                        speech_threshold = noise_floor * speech_threshold_multiplier
                        log_audio(self.logger, f"📊 Noise floor: {noise_floor:.1f} RMS → Speech threshold: {speech_threshold:.1f} RMS ({speech_threshold_multiplier}x)")
                    continue

                # VAD check (WebRTC)
                try:
                    is_speech_vad = self.vad.is_speech(audio_16k.tobytes(), 16000)
                except:
                    is_speech_vad = False

                # Energy-based speech detection
                speech_threshold = noise_floor * speech_threshold_multiplier
                is_speech_energy = energy > speech_threshold

                # Combined decision (both must agree)
                is_speech = is_speech_vad and is_speech_energy

                # Debug logging
                if self.debug and speech_started:
                    log_debug(self.logger, f"Energy: {energy:.1f}, Threshold: {speech_threshold:.1f}, VAD: {is_speech_vad}, Energy: {is_speech_energy}, Speech: {is_speech}")

                # Store frame
                frames.append(data)

                if is_speech:
                    if not speech_started:
                        speech_started = True
                        log_audio(self.logger, f"🗣️  Speech detected (energy: {energy:.1f} > {speech_threshold:.1f})")
                    speech_frame_count += 1
                    silence_frames = 0
                else:
                    if speech_started:
                        silence_frames += 1
                        if self.debug and silence_frames % 10 == 0:
                            log_debug(self.logger, f"Silence frames: {silence_frames}/{silence_frames_threshold} (energy: {energy:.1f})")

                # End detection - enough silence after minimum speech
                if speech_started and silence_frames >= silence_frames_threshold:
                    if speech_frame_count >= min_speech_frames:
                        log_audio(self.logger, f"Recording complete: {elapsed:.1f}s")
                        break

            except Exception as e:
                log_error(self.logger, f"Recording error: {e}")
                break

        if not frames:
            return b""

        return b''.join(frames)

    def record_command(self):
        """Record a command using microphone input with VAD"""
        if self.debug:
            # Return a dummy audio buffer with some speech-like content for testing
            # Create a simple sine wave to simulate speech
            import math
            sample_rate = config.RATE
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
                except:
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