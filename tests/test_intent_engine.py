"""
Intent engine tests (active intents only).
"""

import unittest
from pathlib import Path

from modules.intent_engine import IntentEngine, Intent
from tests.utils.fixture_loader import load_fixture


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestIntentEngine(unittest.TestCase):
    def setUp(self):
        self.engine_en = IntentEngine(fuzzy_threshold=50, language='en', debug=False)
        self.fixtures = load_fixture(FIXTURES_DIR / "intent_smoke_cases_en.json")

    def test_play_music_basic(self):
        for case in self.fixtures["play_music"]:
            with self.subTest(text=case["text"]):
                intent = self.engine_en.classify(case["text"])
                self.assertIsNotNone(intent)
                self.assertEqual(intent.intent_type, 'play_music')
                self.assertEqual(intent.parameters.get('query'), case.get("query"))

    def test_pause_command(self):
        for case in self.fixtures["pause"]:
            with self.subTest(command=case["text"]):
                intent = self.engine_en.classify(case["text"])
                self.assertIsNotNone(intent)
                self.assertEqual(intent.intent_type, 'pause')

    def test_volume_up(self):
        for case in self.fixtures["volume_up"]:
            with self.subTest(command=case["text"]):
                intent = self.engine_en.classify(case["text"])
                self.assertIsNotNone(intent)
                self.assertEqual(intent.intent_type, 'volume_up')

    def test_volume_down(self):
        for case in self.fixtures["volume_down"]:
            with self.subTest(command=case["text"]):
                intent = self.engine_en.classify(case["text"])
                self.assertIsNotNone(intent)
                self.assertEqual(intent.intent_type, 'volume_down')

    def test_fuzzy_typos(self):
        for case in self.fixtures["fuzzy_typos"]:
            with self.subTest(command=case["text"]):
                intent = self.engine_en.classify(case["text"])
                if intent:
                    self.assertIsInstance(intent, Intent)

    def test_empty_text(self):
        for text in ['', '   ', None]:
            with self.subTest(text=text):
                intent = self.engine_en.classify(text)
                self.assertIsNone(intent)

    def test_no_match(self):
        for case in self.fixtures["no_match"]:
            with self.subTest(text=case["text"]):
                intent = self.engine_en.classify(case["text"])
                self.assertIsNone(intent)


class TestIntentEngineFrench(unittest.TestCase):
    def setUp(self):
        self.engine_fr = IntentEngine(fuzzy_threshold=50, language='fr', debug=False)
        self.fixtures = load_fixture(FIXTURES_DIR / "intent_smoke_cases_fr.json")

    def test_play_music_basic_fr(self):
        for case in self.fixtures["play_music"]:
            with self.subTest(text=case["text"]):
                intent = self.engine_fr.classify(case["text"])
                self.assertIsNotNone(intent)
                self.assertEqual(intent.intent_type, 'play_music')
                self.assertEqual(intent.parameters.get('query'), case.get("query"))

    def test_volume_commands_fr(self):
        for case in self.fixtures["volume"]:
            with self.subTest(command=case["text"]):
                intent = self.engine_fr.classify(case["text"])
                self.assertIsNotNone(intent)
                self.assertEqual(intent.intent_type, case["intent"])

        for case in self.fixtures["pause"]:
            with self.subTest(command=case["text"]):
                intent = self.engine_fr.classify(case["text"])
                self.assertIsNotNone(intent)
                self.assertEqual(intent.intent_type, case["intent"])
