#!/usr/bin/env python3
import logging
import time
import pyaudio
import numpy as np
from modules.wake_word import WakeWordDetector
from modules.vad import CommandRecorder
from modules.hailo_stt import HailoSTT
import config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

class VoiceOrchestrator:
    def __init__(self):
        self.audio = pyaudio.PyAudio()
        self.wake_detector = WakeWordDetector()
        self.command_recorder = CommandRecorder(self.audio)
        self.hailo_stt = HailoSTT()
        self.stream = None
        self.last_reset_time = 0
        
    def _reset_and_start_listening(self):
        """Reset wake word detector and start clean listening session"""
        self.wake_detector.reset_after_command()
        self.last_reset_time = time.time()
        
        # Clean restart of audio stream
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            
        self.stream = self.audio.open(
            format=pyaudio.paInt16, channels=config.CHANNELS, rate=config.SAMPLE_RATE,
            input=True, frames_per_buffer=config.CHUNK_SIZE
        )
        
        # Brief delay and buffer clear for clean start
        time.sleep(config.WAKE_WORD_RESET_DELAY)
        for _ in range(10):  # Clear audio buffer
            self.stream.read(config.CHUNK_SIZE, exception_on_overflow=False)
            
        logger.info("Listening for wake word...")
        
    def _process_wake_word_frame(self):
        audio_data = self.stream.read(config.CHUNK_SIZE, exception_on_overflow=False)
        audio_frame = np.frombuffer(audio_data, dtype=np.int16)
        
        # Single grace period after any reset for clean state
        if time.time() - self.last_reset_time < 1.0:  # 1 second grace period
            self.wake_detector.detect(audio_frame)  # Maintain model state
            return False
            
        return self.wake_detector.detect(audio_frame)
        
    def _record_and_process_command(self):
        """Record voice command and process it"""
        # Stop wake word listening
        self.stream.stop_stream()
        self.stream.close()
        self.stream = None
        
        # Record and transcribe
        command_audio = self.command_recorder.record_command()
        if len(command_audio) > 0:
            transcription = self.hailo_stt.transcribe(command_audio)
            if transcription:
                logger.info(f"Command: '{transcription}'")
                return transcription
                
        logger.info("No command detected")
        return ""
        
    def run(self):
        """Simple state machine: Listen -> Wake -> Record -> Process -> Reset -> Listen"""
        logger.info("Voice Assistant starting...")
        
        try:
            self._reset_and_start_listening()
            
            while True:
                if self._process_wake_word_frame():
                    command = self._record_and_process_command()
                    if command:
                        pass  # TODO: Send to Home Assistant
                    self._reset_and_start_listening()
                    
        except KeyboardInterrupt:
            logger.info("Voice Assistant stopping...")
        finally:
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
            self.audio.terminate()
            logger.info("Cleanup completed")

if __name__ == "__main__":
    print("🎤 Pi-Sat Voice Assistant")
    print("Press Ctrl+C to stop")
    print("-" * 30)
    VoiceOrchestrator().run() 