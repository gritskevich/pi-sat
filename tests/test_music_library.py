"""
Tests for MusicLibrary Module

Tests catalog management, fuzzy search, and favorites handling.
"""

import unittest
import os
import tempfile
import shutil
from pathlib import Path
from modules.music_library import MusicLibrary


class TestMusicLibrary(unittest.TestCase):
    """Test MusicLibrary module"""

    def setUp(self):
        """Set up test fixtures"""
        # Create temporary music library
        self.test_dir = tempfile.mkdtemp()

        # Create test music files
        self.test_songs = [
            "Louane - maman.mp3",
            "Louane - Jour 1.mp3",
            "Kids United - On écrit sur les murs.mp3",
            "Stromae - Alors on danse.mp3",
            "MIKA - Grace Kelly.mp3",
        ]

        for song_path in self.test_songs:
            full_path = os.path.join(self.test_dir, song_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            # Create empty file
            Path(full_path).touch()

        # Create MusicLibrary instance
        self.library = MusicLibrary(
            library_path=self.test_dir,
            fuzzy_threshold=50,
            debug=True
        )

    def tearDown(self):
        """Clean up test fixtures"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_initialization(self):
        """Test: MusicLibrary initializes correctly"""
        self.assertEqual(self.library.library_path, self.test_dir)
        self.assertEqual(self.library.fuzzy_threshold, 50)
        self.assertTrue(self.library.is_empty())

    def test_load_from_filesystem(self):
        """Test: Load catalog from filesystem"""
        count = self.library.load_from_filesystem()

        self.assertEqual(count, 5)
        self.assertEqual(self.library.get_catalog_size(), 5)
        self.assertFalse(self.library.is_empty())

    def test_search_exact_match(self):
        """Test: Search with exact match"""
        self.library.load_from_filesystem()

        result = self.library.search("Louane - maman")
        self.assertIsNotNone(result)

        file_path, confidence = result
        self.assertIn("Louane - maman", file_path)
        self.assertGreater(confidence, 0.8)

    def test_search_partial_match(self):
        """Test: Search with partial match"""
        self.library.load_from_filesystem()

        result = self.library.search("louane")
        self.assertIsNotNone(result)

        file_path, confidence = result
        self.assertIn("Louane", file_path)

    def test_search_typo_tolerance(self):
        """Test: Search with typo tolerance"""
        self.library.load_from_filesystem()

        # Typo: "mamann" instead of "maman"
        result = self.library.search("mamann")
        self.assertIsNotNone(result)

        file_path, confidence = result
        self.assertIn("Louane", file_path)

    def test_search_artist(self):
        """Test: Search by artist name"""
        self.library.load_from_filesystem()

        result = self.library.search("kids united")
        self.assertIsNotNone(result)

        file_path, confidence = result
        self.assertIn("Kids United", file_path)

    def test_search_no_match(self):
        """Test: Search with no match"""
        self.library.load_from_filesystem()

        result = self.library.search("nonexistent song xyz")
        # Should return None or a low-confidence match
        # Depending on fuzzy threshold, might return None
        if result:
            _, confidence = result
            self.assertLess(confidence, 0.5)

    def test_search_empty_query(self):
        """Test: Search with empty query"""
        self.library.load_from_filesystem()

        result = self.library.search("")
        self.assertIsNone(result)

        result = self.library.search("   ")
        self.assertIsNone(result)

    def test_search_empty_catalog(self):
        """Test: Search on empty catalog"""
        # Don't load catalog
        result = self.library.search("maman")
        self.assertIsNone(result)

    def test_get_all_songs(self):
        """Test: Get all songs in catalog"""
        self.library.load_from_filesystem()

        all_songs = self.library.get_all_songs()
        self.assertEqual(len(all_songs), 5)

        # Verify all test songs are present
        for song in self.test_songs:
            self.assertIn(song, all_songs)

    def test_clear_cache(self):
        """Test: Clear catalog cache"""
        self.library.load_from_filesystem()
        self.assertEqual(self.library.get_catalog_size(), 5)

        self.library.clear_cache()
        self.assertEqual(self.library.get_catalog_size(), 0)
        self.assertTrue(self.library.is_empty())

    def test_refresh_catalog(self):
        """Test: Refresh catalog"""
        self.library.load_from_filesystem()
        self.assertEqual(self.library.get_catalog_size(), 5)

        # Add a new song
        new_song = os.path.join(self.test_dir, "New Artist/New Song.mp3")
        os.makedirs(os.path.dirname(new_song), exist_ok=True)
        Path(new_song).touch()

        # Clear and refresh
        self.library.clear_cache()
        count = self.library.refresh(source='filesystem')

        self.assertEqual(count, 6)

    def test_favorites_not_found(self):
        """Test: Load favorites when file doesn't exist"""
        # Use a non-existent path to ensure file doesn't exist
        favorites_dir = tempfile.mkdtemp()
        favorites_path = os.path.join(favorites_dir, "nonexistent_favorites.m3u")

        try:
            favorites = self.library.load_favorites(favorites_path)
            self.assertEqual(favorites, [])
        finally:
            shutil.rmtree(favorites_dir)

    def test_add_to_favorites(self):
        """Test: Add song to favorites"""
        # Create temporary favorites file
        favorites_dir = tempfile.mkdtemp()
        favorites_path = os.path.join(favorites_dir, "favorites.m3u")

        try:
            song_path = "Louane - maman.mp3"
            success = self.library.add_to_favorites(song_path, favorites_path=favorites_path)

            self.assertTrue(success)
            self.assertTrue(os.path.exists(favorites_path))

            # Verify content
            with open(favorites_path, 'r') as f:
                content = f.read()
                self.assertIn(song_path, content)

        finally:
            shutil.rmtree(favorites_dir)

    def test_add_duplicate_to_favorites(self):
        """Test: Add same song to favorites twice"""
        favorites_dir = tempfile.mkdtemp()
        favorites_path = os.path.join(favorites_dir, "favorites.m3u")

        try:
            song_path = "Louane - maman.mp3"

            # Add first time
            success1 = self.library.add_to_favorites(song_path, favorites_path=favorites_path)
            self.assertTrue(success1)

            # Add second time (should not duplicate)
            success2 = self.library.add_to_favorites(song_path, favorites_path=favorites_path)
            self.assertTrue(success2)

            # Verify only one entry
            with open(favorites_path, 'r') as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
                self.assertEqual(lines.count(song_path), 1)

        finally:
            shutil.rmtree(favorites_dir)

    def test_load_favorites(self):
        """Test: Load favorites from M3U file"""
        favorites_dir = tempfile.mkdtemp()
        favorites_path = os.path.join(favorites_dir, "favorites.m3u")

        try:
            # Create favorites file
            test_favorites = [
                "Louane - maman.mp3",
                "Kids United - On écrit sur les murs.mp3",
            ]

            with open(favorites_path, 'w') as f:
                for song in test_favorites:
                    f.write(f"{song}\n")

            # Load favorites
            loaded = self.library.load_favorites(favorites_path)

            self.assertEqual(len(loaded), 2)
            self.assertIn(test_favorites[0], loaded)
            self.assertIn(test_favorites[1], loaded)

        finally:
            shutil.rmtree(favorites_dir)


if __name__ == '__main__':
    unittest.main()
