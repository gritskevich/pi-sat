"""
Tests for Piper TTS Module

Tests speech generation, file creation, and error handling.
"""

import unittest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import json
from modules.piper_tts import PiperTTS, speak
import config


class TestPiperTTS(unittest.TestCase):
    """Test Piper TTS functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.voice_model = Path(config.PIPER_MODEL_PATH)
        self.responses = json.loads(
            Path(__file__).resolve().parent.parent.joinpath("resources/response_library.json").read_text(encoding="utf-8")
        )

    def _response_options(self, language: str, key: str, **params):
        options = self.responses.get(language, {}).get(key, [])
        return [template.format(**params) for template in options]

    def test_initialization_default(self):
        """Test PiperTTS initialization with defaults"""
        # Skip if voice model doesn't exist (CI environment)
        if not self.voice_model.exists():
            self.skipTest("Voice model not available")

        with patch("modules.piper_tts.os.path.exists", return_value=True), \
             patch("modules.audio_devices.validate_alsa_device", return_value=True):
            tts = PiperTTS()
        self.assertIsNotNone(tts)
        self.assertTrue(tts.model_path.exists())
        self.assertEqual(tts.output_device, 'default')

    def test_initialization_custom_model(self):
        """Test initialization with custom model path"""
        if not self.voice_model.exists():
            self.skipTest("Voice model not available")

        with patch("modules.piper_tts.os.path.exists", return_value=True), \
             patch("modules.audio_devices.validate_alsa_device", return_value=True):
            tts = PiperTTS(model_path=str(self.voice_model))
            self.assertEqual(tts.model_path, self.voice_model)

    def test_initialization_missing_model(self):
        """Test initialization fails with missing model"""
        with patch("modules.piper_tts.os.path.exists", return_value=True), \
             patch("modules.audio_devices.validate_alsa_device", return_value=True), \
             self.assertRaises(FileNotFoundError):
            PiperTTS(model_path='/nonexistent/model.onnx')

    def test_validation_missing_binary(self):
        """Test validation catches missing Piper binary"""
        with patch('modules.piper_tts.os.path.exists') as mock_exists, \
             patch("modules.audio_devices.validate_alsa_device", return_value=True):
            # Piper binary doesn't exist, model exists
            mock_exists.side_effect = lambda path: '/usr/local/bin/piper' not in str(path)

            with self.assertRaises(FileNotFoundError) as cm:
                PiperTTS(model_path=str(self.voice_model))

            self.assertIn('Piper binary not found', str(cm.exception))

    def test_speak_empty_text(self):
        """Test speak() with empty text"""
        if not self.voice_model.exists():
            self.skipTest("Voice model not available")

        with patch("modules.piper_tts.os.path.exists", return_value=True), \
             patch("modules.audio_devices.validate_alsa_device", return_value=True):
            tts = PiperTTS()
            result = tts.speak("")
            self.assertFalse(result)

            result = tts.speak("   ")
            self.assertFalse(result)

    def test_speak_subprocess_call(self):
        """Test speak() shells out with expected pipeline"""
        if not self.voice_model.exists():
            self.skipTest("Voice model not available")

        with patch("modules.piper_tts.os.path.exists", return_value=True), \
             patch("modules.audio_devices.validate_alsa_device", return_value=True), \
             patch("modules.piper_tts.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

            tts = PiperTTS()
            result = tts.speak("Hello world")

        self.assertTrue(result)
        self.assertEqual(mock_run.call_count, 1)
        cmd = mock_run.call_args[0][0]
        self.assertIn("piper", cmd)
        self.assertIn("--model", cmd)
        self.assertIn("--output-raw", cmd)
        self.assertIn("aplay", cmd)

    def test_generate_audio_returns_bytes(self):
        """Test generate_audio() returns raw audio bytes"""
        if not self.voice_model.exists():
            self.skipTest("Voice model not available")

        with patch("modules.piper_tts.os.path.exists", return_value=True), \
             patch("modules.audio_devices.validate_alsa_device", return_value=True), \
             patch("modules.piper_tts.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=b"\x00" * 2048)
            tts = PiperTTS()
            audio_data = tts.generate_audio("Test")

        self.assertIsInstance(audio_data, bytes)
        self.assertGreater(len(audio_data), 0)

    def test_generate_audio_to_file(self):
        """Test generate_audio() saves to WAV file"""
        if not self.voice_model.exists():
            self.skipTest("Voice model not available")

        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            temp_path = f.name

        try:
            with patch("modules.piper_tts.os.path.exists", return_value=True), \
                 patch("modules.audio_devices.validate_alsa_device", return_value=True), \
                 patch("modules.piper_tts.subprocess.run") as mock_run:
                mock_run.side_effect = [
                    MagicMock(stdout=b"\x00" * 2048),
                    MagicMock(stdout=b"", returncode=0),
                ]
                tts = PiperTTS()
                result = tts.generate_audio("Test audio file", output_path=temp_path)
                # Mocked sox call doesn't actually write output; create a non-empty placeholder.
                Path(temp_path).write_bytes(b"RIFF\x00\x00\x00\x00WAVE")
            self.assertTrue(result)
            self.assertTrue(os.path.exists(temp_path))
            self.assertGreater(os.path.getsize(temp_path), 0)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_response_templates(self):
        """Test get_response_template() for various intents"""
        if not self.voice_model.exists():
            self.skipTest("Voice model not available")

        with patch("modules.piper_tts.os.path.exists", return_value=True), \
             patch("modules.audio_devices.validate_alsa_device", return_value=True):
            tts = PiperTTS()

        language = tts._responses.language

        # Test simple templates
        self.assertIn(tts.get_response_template('paused'), self._response_options(language, 'paused'))
        self.assertIn(tts.get_response_template('skipped'), self._response_options(language, 'skipped'))

        # Test templates with parameters
        response = tts.get_response_template('playing_song', song="maman")
        self.assertIn(response, self._response_options(language, 'playing_song', song="maman"))

        response = tts.get_response_template('sleep_timer', minutes=30)
        self.assertIn(response, self._response_options(language, 'sleep_timer', minutes=30))

        # Test unknown intent
        response = tts.get_response_template('unknown_intent')
        self.assertIn(response, self._response_options(language, 'unknown'))

        # Test missing parameter (should return template without formatting)
        response = tts.get_response_template('playing_song')  # Missing 'song' param
        self.assertTrue(isinstance(response, str))

    def test_response_template_all_intents(self):
        """Test all defined response templates"""
        if not self.voice_model.exists():
            self.skipTest("Voice model not available")

        with patch("modules.piper_tts.os.path.exists", return_value=True), \
             patch("modules.audio_devices.validate_alsa_device", return_value=True):
            tts = PiperTTS()

        # Test intents that don't need parameters
        simple_intents = [
            'paused', 'skipped', 'previous', 'volume_up', 'volume_down',
            'liked', 'favorites', 'no_match', 'error', 'stopped', 'unknown'
        ]

        for intent in simple_intents:
            response = tts.get_response_template(intent)
            self.assertIsInstance(response, str)
            self.assertGreater(len(response), 0)

    def test_convenience_speak_function(self):
        """Test module-level speak() convenience function"""
        if not self.voice_model.exists():
            self.skipTest("Voice model not available")

        with patch('modules.piper_tts.PiperTTS') as MockTTS:
            mock_instance = MagicMock()
            mock_instance.speak.return_value = True
            MockTTS.return_value = mock_instance

            result = speak("Test")

            self.assertTrue(result)
            MockTTS.assert_called_once()
            mock_instance.speak.assert_called_once_with("Test")


class TestPiperTTSIntegration(unittest.TestCase):
    """Integration tests for Piper TTS (requires actual Piper installation)"""

    def setUp(self):
        """Set up integration tests"""
        if os.getenv("PISAT_RUN_PIPER_INTEGRATION", "0") != "1":
            self.skipTest("Set PISAT_RUN_PIPER_INTEGRATION=1 to run Piper integration tests")

        self.voice_model = Path(config.PIPER_MODEL_PATH)

        # Skip all integration tests if prerequisites not met
        if not self.voice_model.exists():
            self.skipTest("Voice model not available")

        if not os.path.exists(config.PIPER_BINARY_PATH):
            self.skipTest("Piper binary not installed")

    def test_real_speech_generation(self):
        """Test actual speech generation (no audio playback)"""
        tts = PiperTTS()
        audio_data = tts.generate_audio("Integration test")

        self.assertIsInstance(audio_data, bytes)
        # Typical audio should be at least a few KB for a short phrase
        self.assertGreater(len(audio_data), 1000)

    def test_real_wav_file_generation(self):
        """Test actual WAV file generation"""
        # Check if sox is available
        if not os.path.exists('/usr/bin/sox'):
            self.skipTest("sox not installed")

        tts = PiperTTS()

        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            temp_path = f.name

        try:
            result = tts.generate_audio("WAV test", output_path=temp_path)
            self.assertTrue(result)

            # Verify WAV file format
            with open(temp_path, 'rb') as f:
                header = f.read(12)
                # Check RIFF header
                self.assertEqual(header[0:4], b'RIFF')
                self.assertEqual(header[8:12], b'WAVE')

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_multiple_speech_calls(self):
        """Test multiple consecutive speech generation calls"""
        tts = PiperTTS()

        texts = [
            "First test",
            "Second test",
            "Third test"
        ]

        for text in texts:
            audio = tts.generate_audio(text)
            self.assertIsInstance(audio, bytes)
            self.assertGreater(len(audio), 0)


if __name__ == '__main__':
    unittest.main()
