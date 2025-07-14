import logging
import time
import numpy as np
import webrtcvad
import config

logger = logging.getLogger(__name__)

class SilenceDetector:
    def __init__(self):
        self.vad = webrtcvad.Vad(config.VAD_AGGRESSIVENESS)
        self.silence_start_time = None
        self.has_speech = False
        self.recording_start_time = None
        
    def process_frame(self, audio_frame, sample_rate=16000):
        """Process audio frame and return if speech is detected"""
        # Convert numpy array to bytes if needed
        if isinstance(audio_frame, np.ndarray):
            audio_bytes = audio_frame.astype(np.int16).tobytes()
        else:
            audio_bytes = audio_frame
            
        # Check if frame contains speech
        is_speech = self.vad.is_speech(audio_bytes, sample_rate)
        current_time = time.time()
        
        if is_speech:
            self.has_speech = True
            self.silence_start_time = None
            return True
        else:
            # Silence detected
            if self.silence_start_time is None:
                self.silence_start_time = current_time
            return False
    
    def should_stop_recording(self):
        """Check if recording should stop due to silence duration"""
        current_time = time.time()
        
        # If no speech detected yet and timeout has passed, stop
        if not self.has_speech and self.recording_start_time:
            if current_time - self.recording_start_time >= config.INITIAL_SILENCE_TIMEOUT:
                return True
        
        # If speech was detected, use normal silence timeout
        if not self.has_speech:
            return False  # No speech detected yet, keep recording (until timeout above)
            
        if self.silence_start_time is None:
            return False  # Currently hearing speech
            
        silence_duration = current_time - self.silence_start_time
        return silence_duration >= config.SILENCE_DURATION
    
    def reset(self):
        """Reset detector state for new recording session"""
        self.silence_start_time = None
        self.has_speech = False
        self.recording_start_time = time.time()

class CommandRecorder:
    def __init__(self, audio_interface):
        self.audio = audio_interface
        self.detector = SilenceDetector()
        
    def record_command(self):
        """Record command with VAD-based silence detection"""
        logger.info("Recording command...")
        
        stream = self.audio.open(
            format=self.audio.get_format_from_width(2),  # 16-bit
            channels=config.CHANNELS,
            rate=config.SAMPLE_RATE,
            input=True,
            frames_per_buffer=config.CHUNK_SIZE
        )
        
        audio_buffer = []
        self.detector.reset()
        start_time = time.time()
        
        try:
            while True:
                # Check max duration timeout
                if time.time() - start_time >= config.MAX_RECORDING_DURATION:
                    logger.info("Max recording duration reached")
                    break
                
                # Read audio chunk
                audio_data = stream.read(config.CHUNK_SIZE, exception_on_overflow=False)
                audio_frame = np.frombuffer(audio_data, dtype=np.int16)
                audio_buffer.append(audio_frame)
                
                # Process with VAD
                self.detector.process_frame(audio_frame)
                
                # Check if should stop due to silence
                if self.detector.should_stop_recording():
                    if not self.detector.has_speech:
                        logger.info("No speech detected after wake word, stopping")
                    else:
                        logger.info("Silence detected, ending recording")
                    break
                    
        except Exception as e:
            logger.error(f"Error during recording: {e}")
        finally:
            stream.stop_stream()
            stream.close()
        
        # Combine all audio chunks
        if audio_buffer:
            full_audio = np.concatenate(audio_buffer)
            duration = len(full_audio) / config.SAMPLE_RATE
            logger.info(f"Recorded {duration:.2f} seconds of audio")
            return full_audio
        else:
            logger.warning("No audio recorded")
            return np.array([], dtype=np.int16) 