#!/usr/bin/env python3
"""
Test Hailo STT language detection with French and English audio.

This test uses real Hailo STT transcription (no mocking) to verify
that the language configuration works correctly.
"""

import unittest
import os
import sys
from pathlib import Path
import soundfile as sf
import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from modules.hailo_stt import HailoSTT


class TestLanguageDetection(unittest.TestCase):
    """Test STT language detection with real Hailo transcription."""

    @classmethod
    def setUpClass(cls):
        if os.getenv("PISAT_RUN_HAILO_TESTS", "0") != "1":
            raise unittest.SkipTest("Set PISAT_RUN_HAILO_TESTS=1 to run Hailo hardware tests")

        """Verify fixtures exist (STT is created per-test to allow language switching)."""
        cls.project_root = Path(__file__).parent.parent
        cls.french_dir = cls.project_root / "tests" / "audio_samples" / "language_tests" / "french"
        cls.english_dir = cls.project_root / "tests" / "audio_samples" / "language_tests" / "english"

        # Check if audio files exist
        if not cls.french_dir.exists() or not cls.english_dir.exists():
            raise unittest.SkipTest("Language test audio files not found. Run scripts/generate_language_test_audio.py first.")

        print(f"\n{'='*60}")
        print(f"Language Detection Test")
        print(f"Languages: fr, en")
        print(f"{'='*60}\n")

    def _load_audio(self, audio_path):
        """Load audio file and convert to bytes."""
        audio_data, sample_rate = sf.read(audio_path)

        # Convert to 16-bit PCM if needed
        if audio_data.dtype != np.int16:
            audio_data = (audio_data * 32767).astype(np.int16)

        return audio_data.tobytes()

    def _test_audio_file(self, stt: HailoSTT, audio_path, expected_keywords, language_name):
        """Test a single audio file."""
        print(f"\n  Testing: {audio_path.name}")

        audio_data = self._load_audio(audio_path)
        transcription = stt.transcribe(audio_data)

        print(f"    Transcription: '{transcription}'")

        # Check if transcription is not empty
        self.assertIsNotNone(transcription, f"Transcription should not be None for {audio_path.name}")

        if not transcription or not transcription.strip():
            print(f"    ⚠️  Warning: Empty transcription for {audio_path.name}")
            return False

        # Check if any expected keyword is in transcription (case-insensitive)
        transcription_lower = transcription.lower()
        found_keyword = any(keyword.lower() in transcription_lower for keyword in expected_keywords)

        if found_keyword:
            print(f"    ✅ Match found (keywords: {expected_keywords})")
            return True
        else:
            print(f"    ❌ No keyword match (expected: {expected_keywords})")
            return False

    def test_french_audio_with_french_stt(self):
        """Test: French audio files transcribed with French STT."""
        print(f"\n{'='*60}")
        print("French Audio → French STT")
        print(f"{'='*60}")

        stt = HailoSTT(debug=True, language="fr")
        if not stt.is_available():
            self.skipTest("Hailo STT not available")

        # Define expected keywords for each French test file
        french_tests = {
            "bonjour.wav": ["bonjour", "comment", "allez"],
            "merci.wav": ["merci", "beaucoup"],
            "musique.wav": ["musique", "joue"],
            "volume.wav": ["volume", "monte"],
            "pause.wav": ["pause"],
            "suivant.wav": ["suivant", "chanson"],
            "arrete.wav": ["arrête", "arret", "musique"],
            "favoris.wav": ["favoris", "chanson"],
            "question.wav": ["heure", "quelle"],
            "belle_journee.wav": ["belle", "journée", "journee"],
        }

        results = []
        try:
            for filename, keywords in french_tests.items():
                audio_path = self.french_dir / filename
                if audio_path.exists():
                    success = self._test_audio_file(stt, audio_path, keywords, "French")
                    results.append(success)
        finally:
            stt.cleanup()

        # Calculate success rate
        success_count = sum(results)
        total_count = len(results)
        success_rate = (success_count / total_count * 100) if total_count > 0 else 0

        print(f"\n{'='*60}")
        print(f"French Results: {success_count}/{total_count} ({success_rate:.1f}% success)")
        print(f"{'='*60}")

        # Assert at least 60% success rate (allowing for some TTS/STT imperfection)
        self.assertGreaterEqual(success_rate, 60.0,
                              f"French transcription success rate too low: {success_rate:.1f}%")

    def test_english_audio_with_english_stt(self):
        """Test: English audio files transcribed with English STT."""
        print(f"\n{'='*60}")
        print("English Audio → English STT")
        print(f"{'='*60}")

        stt = HailoSTT(debug=True, language="en")
        if not stt.is_available():
            self.skipTest("Hailo STT not available")

        # Define expected keywords for each English test file
        english_tests = {
            "hello.wav": ["hello", "how", "are"],
            "thanks.wav": ["thank", "you"],
            "play_music.wav": ["play", "music"],
            "volume_up.wav": ["volume", "up", "turn"],
            "pause.wav": ["pause"],
            "next.wav": ["next", "song"],
            "stop.wav": ["stop"],
            "favorites.wav": ["favorite", "add", "song"],
            "question.wav": ["time", "what"],
            "nice_day.wav": ["beautiful", "day", "nice"],
        }

        results = []
        try:
            for filename, keywords in english_tests.items():
                audio_path = self.english_dir / filename
                if audio_path.exists():
                    success = self._test_audio_file(stt, audio_path, keywords, "English")
                    results.append(success)
        finally:
            stt.cleanup()

        # Calculate success rate
        success_count = sum(results)
        total_count = len(results)
        success_rate = (success_count / total_count * 100) if total_count > 0 else 0

        print(f"\n{'='*60}")
        print(f"English Results: {success_count}/{total_count} ({success_rate:.1f}% success)")
        print(f"{'='*60}")

        # Assert at least 60% success rate (allowing for some TTS/STT imperfection)
        self.assertGreaterEqual(success_rate, 60.0,
                              f"English transcription success rate too low: {success_rate:.1f}%")

    def test_language_mismatch_detection(self):
        """Test: Detect when audio language doesn't match STT language."""
        print(f"\n{'='*60}")
        print("Language Mismatch Detection")
        print("This test is informational only")
        print(f"{'='*60}")

        # French STT on English audio
        audio_path = self.english_dir / "hello.wav"
        stt_fr = HailoSTT(debug=True, language="fr")
        try:
            if stt_fr.is_available() and audio_path.exists():
                audio_data = self._load_audio(audio_path)
                transcription = stt_fr.transcribe(audio_data)
                print(f"\n  English audio with FR STT: {audio_path.name}")
                print(f"    '{transcription}'")
        finally:
            stt_fr.cleanup()

        # English STT on French audio
        audio_path = self.french_dir / "bonjour.wav"
        stt_en = HailoSTT(debug=True, language="en")
        try:
            if stt_en.is_available() and audio_path.exists():
                audio_data = self._load_audio(audio_path)
                transcription = stt_en.transcribe(audio_data)
                print(f"\n  French audio with EN STT: {audio_path.name}")
                print(f"    '{transcription}'")
        finally:
            stt_en.cleanup()

        print(f"\n  ✅ Mismatch test completed (informational only)")


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
