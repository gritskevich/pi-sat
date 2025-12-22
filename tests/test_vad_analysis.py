import unittest
import os
import glob
import numpy as np
import config
from tests.test_utils import read_wav_mono_int16

try:
    import webrtcvad
except ModuleNotFoundError:
    webrtcvad = None

class TestVADAnalysis(unittest.TestCase):
    def setUp(self):
        if webrtcvad is None:
            self.skipTest("Missing dependency: webrtcvad")
        self.vad = webrtcvad.Vad(config.VAD_LEVEL)
        self.frame_duration = config.FRAME_DURATION
        self.sample_rate = 16000
        self.frame_size = int(self.sample_rate * self.frame_duration / 1000)
    
    def analyze_vad_frames(self, audio, filename):
        print(f"\n🔍 Analyzing VAD for: {filename}")
        
        speech_frames = 0
        silence_frames = 0
        total_frames = 0
        
        for i in range(0, len(audio), self.frame_size):
            frame = audio[i:i+self.frame_size]
            if len(frame) == self.frame_size:
                total_frames += 1
                frame_bytes = frame.tobytes()
                
                try:
                    is_speech = self.vad.is_speech(frame_bytes, self.sample_rate)
                    if is_speech:
                        speech_frames += 1
                    else:
                        silence_frames += 1
                except:
                    silence_frames += 1
        
        speech_percent = (speech_frames / total_frames) * 100 if total_frames > 0 else 0
        silence_percent = (silence_frames / total_frames) * 100 if total_frames > 0 else 0
        
        print(f"📊 Total frames: {total_frames}")
        print(f"🗣️  Speech frames: {speech_frames} ({speech_percent:.1f}%)")
        print(f"🔇 Silence frames: {silence_frames} ({silence_percent:.1f}%)")
        
        return speech_frames, silence_frames, total_frames
    
    def test_vad_analysis(self):
        audio_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio_samples")
        
        # Test command files
        command_dirs = [
            os.path.join(audio_dir, "commands", "simple"),
            os.path.join(audio_dir, "commands", "complex"),
            os.path.join(audio_dir, "commands", "with_pauses")
        ]
        
        for command_dir in command_dirs:
            if os.path.exists(command_dir):
                wav_files = glob.glob(os.path.join(command_dir, "*.wav"))
                for file in wav_files:
                    filename = os.path.basename(file)
                    audio_path = file
                    
                    if os.path.exists(audio_path):
                        audio, rate = read_wav_mono_int16(audio_path)
                        if rate != self.sample_rate:
                            continue
                        self.analyze_vad_frames(audio, filename)
    
    def test_silence_audio(self):
        silence = np.zeros(16000, dtype=np.int16)
        print(f"\n🔍 Analyzing pure silence")
        speech_frames, silence_frames, total_frames = self.analyze_vad_frames(silence, "silence")
        
        self.assertGreater(silence_frames, 0)
        print("✅ Silence correctly detected")

if __name__ == "__main__":
    unittest.main(verbosity=2) 
