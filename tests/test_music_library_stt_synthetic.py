import os
import unittest
from collections import OrderedDict
from pathlib import Path

from modules.music_library import MusicLibrary
from tests.utils.fixture_loader import load_fixture


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "music_library_stt_cases_fr.json"


class TestMusicLibrarySttSynthetic(unittest.TestCase):
    def setUp(self):
        self.fixture = load_fixture(FIXTURE_PATH)
        self.catalog = self.fixture["catalog"]
        self.cases = self.fixture["cases"]
        self.library = self._build_library()

    def _build_library(self) -> MusicLibrary:
        library = MusicLibrary(library_path=None, fuzzy_threshold=50, debug=False)
        catalog = []
        metadata = []
        for file_path in self.catalog:
            basename = os.path.splitext(os.path.basename(file_path))[0]
            variants = library._build_searchable_variants(basename)
            catalog.append(file_path)
            metadata.append((file_path, variants))

        library._catalog = catalog
        library._catalog_metadata = metadata
        library._search_best_cache = OrderedDict()
        if library._phonetic_encoder:
            library._phonetic_encoder.clear_cache()
        return library

    def test_search_best_misread_stt_fr(self):
        self.assertEqual(len(self.cases), 60)
        for case in self.cases:
            query = case["query"]
            expect_file = case["expect_file"]
            with self.subTest(query=query):
                result = self.library.search_best(query)
                self.assertIsNotNone(result)
                file_path, confidence = result
                self.assertEqual(file_path, expect_file)
                self.assertGreater(confidence, 0.0)


if __name__ == "__main__":
    unittest.main()
