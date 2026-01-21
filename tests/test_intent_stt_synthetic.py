import unittest
import os
from collections import OrderedDict
from pathlib import Path

from modules.intent_engine import IntentEngine
from modules.music_library import MusicLibrary
from tests.utils.fixture_loader import load_fixture


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "intent_stt_synthetic_fr.json"
CATALOG_PATH = Path(__file__).parent / "fixtures" / "intent_music_cases_fr.json"


class TestIntentSttSynthetic(unittest.TestCase):
    def setUp(self):
        self.engine = IntentEngine(fuzzy_threshold=50, language="fr", debug=False)
        self.fixture = load_fixture(FIXTURE_PATH)
        self.catalog = load_fixture(CATALOG_PATH)["catalog"]
        self.play_cases = self.fixture["play_cases"]
        self.play_no_query = self.fixture.get("play_no_query", [])
        self.control_cases = self.fixture["control_cases"]
        self.no_match_cases = self.fixture.get("no_match", [])
        self.library = self._build_library()
        self.expected_filename = {item["id"]: item["file"] for item in self.catalog}

    def _build_library(self) -> MusicLibrary:
        library = MusicLibrary(library_path=None, fuzzy_threshold=50, debug=False)
        catalog = []
        metadata = []
        for item in self.catalog:
            file_path = item["file"]
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

    def test_play_cases(self):
        self.assertEqual(len(self.play_cases), 31)
        for case in self.play_cases:
            text = case["text"]
            expected_id = case["expect_id"]
            with self.subTest(text=text):
                intent = self.engine.classify(text)
                self.assertIsNotNone(intent)
                self.assertEqual(intent.intent_type, "play_music")
                query = intent.parameters.get("query", "")
                self.assertTrue(query)

                filename_match = self.library.search_best(query)
                self.assertIsNotNone(filename_match)
                self.assertEqual(filename_match[0], self.expected_filename[expected_id])

    def test_control_cases(self):
        self.assertEqual(len(self.control_cases), 21)
        for case in self.control_cases:
            text = case["text"]
            expected = case["expect_intent"]
            with self.subTest(text=text):
                intent = self.engine.classify(text)
                self.assertIsNotNone(intent)
                self.assertEqual(intent.intent_type, expected)

    def test_play_no_query_cases(self):
        for case in self.play_no_query:
            text = case["text"]
            with self.subTest(text=text):
                intent = self.engine.classify(text)
                self.assertIsNotNone(intent)
                self.assertEqual(intent.intent_type, "play_music")
                query = intent.parameters.get("query", "")
                self.assertEqual(query, "")

    def test_no_match_cases(self):
        for case in self.no_match_cases:
            text = case["text"]
            with self.subTest(text=text):
                intent = self.engine.classify(text)
                self.assertIsNone(intent)

    def test_total_count(self):
        total = len(self.play_cases) + len(self.control_cases) + len(self.play_no_query) + len(self.no_match_cases)
        self.assertEqual(total, 54)
