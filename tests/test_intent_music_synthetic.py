import unittest
import os
from collections import OrderedDict
from pathlib import Path

from modules.intent_engine import IntentEngine
from modules.music_library import MusicLibrary
from tests.utils.fixture_loader import load_fixture


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "intent_music_cases_fr.json"


class TestIntentMusicSynthetic(unittest.TestCase):
    def setUp(self):
        self.engine = IntentEngine(fuzzy_threshold=50, language="fr", debug=False)
        self.fixture = self._load_fixture()
        self.catalog = self.fixture["catalog"]
        self.play_cases = self.fixture["play_cases"]
        self.control_cases = self.fixture["control_cases"]
        self.filename_library = self._build_library(use_tags=False)
        self.tag_library = self._build_library(use_tags=True)
        self.expected_filename = {item["id"]: item["file"] for item in self.catalog}
        self.expected_tag = {item["id"]: os.path.join("tags", f"{item['id']}.mp3") for item in self.catalog}

    def _load_fixture(self) -> dict:
        return load_fixture(FIXTURE_PATH)

    def _build_library(self, use_tags: bool) -> MusicLibrary:
        library = MusicLibrary(library_path=None, fuzzy_threshold=50, debug=False)
        catalog = []
        metadata = []
        for item in self.catalog:
            if use_tags:
                file_path = os.path.join("tags", f"{item['id']}.mp3")
                basename = os.path.splitext(os.path.basename(file_path))[0]
                tag_variants = library._collect_tag_variants(item["title"], item["artist"], None)
                variants = library._build_searchable_variants(basename, tag_variants)
            else:
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

    def test_play_music_misread_stt(self):
        self.assertEqual(len(self.play_cases), 46)
        for case in self.play_cases:
            text = case["text"]
            expected_id = case["expect_id"]
            with self.subTest(text=text):
                intent = self.engine.classify(text)
                self.assertIsNotNone(intent)
                self.assertEqual(intent.intent_type, "play_music")
                query = intent.parameters.get("query", "")
                self.assertTrue(query)
                if "s'il" in text or "stp" in text:
                    self.assertNotIn("s'il", query)
                    self.assertNotIn("stp", query)

                filename_match = self.filename_library.search_best(query)
                self.assertIsNotNone(filename_match)
                self.assertEqual(filename_match[0], self.expected_filename[expected_id])

                tag_match = self.tag_library.search_best(query)
                self.assertIsNotNone(tag_match)
                self.assertEqual(tag_match[0], self.expected_tag[expected_id])

    def test_control_intents_misread_stt(self):
        self.assertEqual(len(self.control_cases), 19)
        for case in self.control_cases:
            text = case["text"]
            expected = case["expect_intent"]
            with self.subTest(text=text):
                intent = self.engine.classify(text)
                self.assertIsNotNone(intent)
                self.assertEqual(intent.intent_type, expected)
