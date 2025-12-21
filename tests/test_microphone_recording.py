import sys
import os
import time
import pyaudio
import numpy as np
from modules.speech_recorder import SpeechRecorder
import config

def test_microphone_recording():
    print("🎤 Testing real microphone recording with debug playback")
    print("Speak after the beep...")
    
    recorder = SpeechRecorder(debug=True)
    p = pyaudio.PyAudio()
    
    stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=16000,
        input=True,
        frames_per_buffer=config.CHUNK
    )
    
    print("🔊 BEEP! (Recording for 5 seconds...)")
    
    frames = []
    for _ in range(0, int(16000 / config.CHUNK * 5)):
        data = stream.read(config.CHUNK)
        frames.append(data)
    
    stream.stop_stream()
    stream.close()
    p.terminate()
    
    print("⏹️  Recording complete. Processing with VAD...")
    
    audio_data = b''.join(frames)
    audio_array = np.frombuffer(audio_data, dtype=np.int16)
    
    result = recorder.process_audio_chunks(audio_array, 16000)
    
    print(f"✅ Processed {len(result)} bytes of speech")
    print("🎧 You should hear the processed audio playback above")

if __name__ == "__main__":
    test_microphone_recording() 