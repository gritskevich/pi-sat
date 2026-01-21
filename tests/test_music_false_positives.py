"""
Tests for MusicLibrary False Positives

Ensures that non-music queries don't accidentally match songs.
This is critical to prevent "turn off the lights" from playing music.
"""

import unittest
import os
import tempfile
import shutil
from pathlib import Path

from modules.music_library import MusicLibrary
from tests.utils.fixture_loader import load_fixture


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "music_false_positive_cases.json"


class TestMusicFalsePositives(unittest.TestCase):
    """Test that non-music queries are rejected"""

    def setUp(self):
        """Set up test fixtures"""
        self.fixture = load_fixture(FIXTURE_PATH)
        # Create temporary music library
        self.test_dir = tempfile.mkdtemp()

        # Create realistic test music files
        self.test_songs = self.fixture["songs"]

        for song_path in self.test_songs:
            full_path = os.path.join(self.test_dir, song_path)
            Path(full_path).touch()

        # Create MusicLibrary with threshold 60 (prevents false positives)
        self.library = MusicLibrary(
            library_path=self.test_dir,
            fuzzy_threshold=60,  # Higher threshold to reject non-music queries
            phonetic_enabled=True,
            debug=False
        )
        self.library.load_from_filesystem()

    def tearDown(self):
        """Clean up test fixtures"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_reject_unrelated_commands(self):
        """Test: Non-music commands should be rejected"""
        for query in self.fixture["unrelated_queries"]:
            result = self.library.search(query)
            self.assertIsNone(
                result,
                f"Non-music query '{query}' should be rejected, but matched: {result}"
            )

    def test_accept_music_queries(self):
        """Test: Real music queries should still match"""
        for case in self.fixture["music_queries"]:
            result = self.library.search(case["query"])
            self.assertIsNotNone(
                result,
                f"Music query '{case['query']}' should match something"
            )
            file_path, confidence = result
            self.assertIn(
                case["expect_contains"],
                file_path,
                f"Query '{case['query']}' should match '{case['expect_contains']}', got '{file_path}'"
            )

    def test_accept_stt_errors(self):
        """Test: Common STT errors should still match songs"""
        for case in self.fixture["stt_errors"]:
            result = self.library.search(case["query"])
            self.assertIsNotNone(
                result,
                f"STT error '{case['query']}' should still match"
            )
            file_path, confidence = result
            self.assertIn(
                case["expect_contains"],
                file_path,
                f"Query '{case['query']}' should match '{case['expect_contains']}', got '{file_path}'"
            )

    def test_threshold_effectiveness(self):
        """Test: Threshold 60 blocks false positives but allows real matches"""
        # False positive (should be blocked)
        fp_result = self.library.search('turn off the lights')
        self.assertIsNone(fp_result, "False positive should be blocked")

        # True positive (should pass)
        tp_result = self.library.search('astronomia')
        self.assertIsNotNone(tp_result, "True positive should pass")
        self.assertGreater(tp_result[1], 0.6, "Confidence should be > 60%")

    def test_search_best_always_returns(self):
        """Test: search_best() always returns something (ignores threshold)"""
        # Even unrelated queries return *something* with search_best()
        result = self.library.search_best('random gibberish xyz')
        self.assertIsNotNone(result, "search_best() should always return something")

        file_path, confidence = result
        # But confidence should be low for unrelated queries
        self.assertLess(
            confidence,
            0.6,
            f"Unrelated query should have low confidence, got {confidence:.1%}"
        )


if __name__ == '__main__':
    unittest.main()
