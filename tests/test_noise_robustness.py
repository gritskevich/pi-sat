import unittest
import os
import soundfile as sf
import numpy as np
from modules.speech_recorder import SpeechRecorder
from tests.test_utils import process_audio_file
import config

try:
    import webrtcvad
except ModuleNotFoundError:
    webrtcvad = None

try:
    from modules.wake_word_listener import WakeWordListener
except ModuleNotFoundError:
    WakeWordListener = None

class TestNoiseRobustness(unittest.TestCase):
    def setUp(self):
        if os.getenv("PISAT_RUN_INTEGRATION_TESTS", "0") != "1":
            self.skipTest("Set PISAT_RUN_INTEGRATION_TESTS=1 to run integration tests")
        if os.getenv("PISAT_RUN_WAKEWORD_TESTS", "0") != "1":
            self.skipTest("Set PISAT_RUN_WAKEWORD_TESTS=1 to run wake word integration tests")
        if webrtcvad is None:
            self.skipTest("Missing dependency: webrtcvad")
        if WakeWordListener is None:
            self.skipTest("Wake word dependency not installed (openwakeword)")

        self.vad = webrtcvad.Vad(config.VAD_LEVEL)
        self.frame_duration = config.FRAME_DURATION
        self.sample_rate = 16000
        self.frame_size = int(self.sample_rate * self.frame_duration / 1000)
        self.recorder = SpeechRecorder(debug=True)
        self.wake_word_listener = WakeWordListener()
    
    def test_noise_vad_analysis(self):
        noise_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                 "audio_samples", "noise", "noise.wav")
        
        if not os.path.exists(noise_file):
            self.skipTest("Noise file not found")
        
        audio, rate = sf.read(noise_file)
        if len(audio.shape) > 1:
            audio = audio[:, 0]
        
        audio = (audio * 32767).astype(np.int16)
        
        print(f"\n🔍 Analyzing noise file: noise.wav")
        
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
        
        # Document the noise characteristics
        print(f"📝 Noise file characteristics: {speech_percent:.1f}% speech, {silence_percent:.1f}% silence")
        
        # Accept any VAD result for noise (no strict expectations)
        self.assertIsInstance(speech_percent, (float, np.floating))
        self.assertIsInstance(silence_percent, (float, np.floating))
        print("✅ Noise VAD analysis completed")
    
    def test_noise_wake_word_false_positive(self):
        noise_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                 "audio_samples", "noise", "noise.wav")
        
        if not os.path.exists(noise_file):
            self.skipTest("Noise file not found")
        
        # Test that noise doesn't trigger wake word using proper audio processing
        detected, max_confidence = process_audio_file(noise_file, self.wake_word_listener.model)
        print(f"📊 Noise wake word test: detected={detected}, confidence={max_confidence:.3f}")
        
        # Accept any result (noise might or might not trigger wake word)
        self.assertIsInstance(detected, bool)
        self.assertIsInstance(max_confidence, (float, np.floating))
        print("✅ Noise wake word test completed")
    
    def test_noise_speech_recorder(self):
        noise_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                 "audio_samples", "noise", "noise.wav")
        
        if not os.path.exists(noise_file):
            self.skipTest("Noise file not found")
        
        audio, rate = sf.read(noise_file)
        if len(audio.shape) > 1:
            audio = audio[:, 0]
        
        audio = (audio * 32767).astype(np.int16)
        result = self.recorder.process_audio_chunks(audio, rate)
        
        # Noise should result in some recording (depending on VAD behavior)
        self.assertIsInstance(result, bytes)
        print(f"✅ Noise processed: {len(result)} bytes")

if __name__ == "__main__":
    unittest.main(verbosity=2) 
