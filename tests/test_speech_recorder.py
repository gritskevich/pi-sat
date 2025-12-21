import unittest
import os
import soundfile as sf
import numpy as np
import glob
from modules.speech_recorder import SpeechRecorder
import config

class TestSpeechRecorder(unittest.TestCase):
    def setUp(self):
        self.recorder = SpeechRecorder(debug=True)
    
    def test_record_from_audio_file(self):
        audio_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio_samples")
        
        # Test command files
        command_dirs = [
            os.path.join(audio_dir, "commands", "simple"),
            os.path.join(audio_dir, "commands", "complex"),
            os.path.join(audio_dir, "commands", "with_pauses")
        ]
        
        results = {}
        for command_dir in command_dirs:
            if os.path.exists(command_dir):
                wav_files = glob.glob(os.path.join(command_dir, "*.wav"))
                for file in wav_files:
                    filename = os.path.basename(file)
                    audio_path = file
                    
                    if os.path.exists(audio_path):
                        audio, rate = sf.read(audio_path)
                        if len(audio.shape) > 1:
                            audio = audio[:, 0]
                        
                        audio = (audio * 32767).astype(np.int16)
                        result = self.recorder.process_audio_chunks(audio, rate)
                        
                        self.assertIsInstance(result, bytes)
                        self.assertGreater(len(result), 0)
                        results[filename] = len(result)
                        print(f"Processed {filename}: {len(result)} bytes")
        
        # Verify different results based on pause position
        if len(results) >= 3:
            simple_files = [f for f in results.keys() if "simple" in f or "kitchen" in f]
            pause_files = [f for f in results.keys() if "pause" in f]
            
            if simple_files and pause_files:
                simple_result = results[simple_files[0]]
                pause_result = results[pause_files[0]]
                
                print(f"\n📊 Results comparison:")
                print(f"Simple command: {simple_result} bytes")
                print(f"Pause command: {pause_result} bytes")
                
                # Files should have different results due to pause detection
                self.assertNotEqual(simple_result, pause_result, "Simple and pause commands should be different")
    
    def test_silence_detection(self):
        silence = np.zeros(16000, dtype=np.int16)
        result = self.recorder.process_audio_chunks(silence, 16000)
        self.assertIsInstance(result, bytes)
    
    def test_short_audio(self):
        short_audio = np.random.randint(-1000, 1000, 8000, dtype=np.int16)
        result = self.recorder.process_audio_chunks(short_audio, 16000)
        self.assertIsInstance(result, bytes)

if __name__ == "__main__":
    unittest.main(verbosity=2) 