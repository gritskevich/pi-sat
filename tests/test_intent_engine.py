"""
Intent engine tests (active intents only).
"""

import unittest

from modules.intent_engine import IntentEngine, Intent


class TestIntentEngine(unittest.TestCase):
    def setUp(self):
        self.engine_en = IntentEngine(fuzzy_threshold=50, language='en', debug=False)

    def test_play_music_basic(self):
        intent = self.engine_en.classify("play maman")
        self.assertIsNotNone(intent)
        self.assertEqual(intent.intent_type, 'play_music')
        self.assertEqual(intent.parameters.get('query'), 'maman')

    def test_stop_command(self):
        for command in ['stop music', 'stop playing']:
            with self.subTest(command=command):
                intent = self.engine_en.classify(command)
                self.assertIsNotNone(intent)
                self.assertEqual(intent.intent_type, 'stop')

    def test_volume_up(self):
        for command in ['louder', 'volume up', 'turn it up']:
            with self.subTest(command=command):
                intent = self.engine_en.classify(command)
                self.assertIsNotNone(intent)
                self.assertEqual(intent.intent_type, 'volume_up')

    def test_volume_down(self):
        for command in ['quieter', 'volume down', 'turn it down']:
            with self.subTest(command=command):
                intent = self.engine_en.classify(command)
                self.assertIsNotNone(intent)
                self.assertEqual(intent.intent_type, 'volume_down')

    def test_fuzzy_typos(self):
        test_cases = ["pley maman", "volum up", "stp music"]
        for command in test_cases:
            with self.subTest(command=command):
                intent = self.engine_en.classify(command)
                if intent:
                    self.assertIsInstance(intent, Intent)

    def test_empty_text(self):
        for text in ['', '   ', None]:
            with self.subTest(text=text):
                intent = self.engine_en.classify(text)
                self.assertIsNone(intent)

    def test_no_match(self):
        intent = self.engine_en.classify("tell me a joke")
        self.assertIsNone(intent)

    def test_case_insensitive(self):
        commands = ["PLAY MAMAN", "Play maman", "play maman", "pLaY mAmAn"]
        for command in commands:
            with self.subTest(command=command):
                intent = self.engine_en.classify(command)
                self.assertIsNotNone(intent)
                self.assertEqual(intent.intent_type, 'play_music')


class TestIntentEngineFrench(unittest.TestCase):
    def setUp(self):
        self.engine_fr = IntentEngine(fuzzy_threshold=50, language='fr', debug=False)

    def test_play_music_basic_fr(self):
        intent = self.engine_fr.classify("joue maman")
        self.assertIsNotNone(intent)
        self.assertEqual(intent.intent_type, 'play_music')
        self.assertEqual(intent.parameters.get('query'), 'maman')

    def test_volume_commands_fr(self):
        cases = [
            ("plus fort", "volume_up"),
            ("moins fort", "volume_down"),
            ("arrete la musique", "stop"),
        ]
        for command, expected_intent in cases:
            with self.subTest(command=command):
                intent = self.engine_fr.classify(command)
                self.assertIsNotNone(intent)
                self.assertEqual(intent.intent_type, expected_intent)
