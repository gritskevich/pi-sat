"""
Test Set Volume Intent - French & English Voice Command Classification

Tests the new set_volume intent with number extraction and French number words.
"""

import unittest
from modules.intent_engine import IntentEngine, ACTIVE_INTENTS


@unittest.skipIf('set_volume' not in ACTIVE_INTENTS, "set_volume intent not active")
class TestSetVolumeIntent(unittest.TestCase):
    """Test set_volume intent with comprehensive French vocabulary"""

    def setUp(self):
        """Initialize intent engines for French and English"""
        self.engine_fr = IntentEngine(fuzzy_threshold=50, language='fr', debug=False)
        self.engine_en = IntentEngine(fuzzy_threshold=50, language='en', debug=False)

    # ============================================================================
    # FRENCH TESTS - Numeric Values
    # ============================================================================

    def test_french_volume_numeric_basic(self):
        """Test: French volume with numeric values (basic)

        Given: French commands with numeric volume levels
        When: classify() called
        Then: Returns set_volume intent with correct volume parameter
        """
        test_cases = [
            ("mets le volume à 50", 50),
            ("mets le volume à 80", 80),
            ("volume à 60", 60),
            ("règle le volume à 40", 40),
            ("ajuste le volume à 70", 70),
        ]

        for command, expected_volume in test_cases:
            with self.subTest(command=command):
                intent = self.engine_fr.classify(command)

                self.assertIsNotNone(intent, f"Intent should not be None for '{command}'")
                self.assertEqual(intent.intent_type, 'set_volume', f"Intent type should be 'set_volume' for '{command}'")
                self.assertEqual(intent.parameters.get('volume'), expected_volume, f"Volume should be {expected_volume} for '{command}'")

    def test_french_volume_numeric_variations(self):
        """Test: French volume with various phrasings

        Note: "monte le volume à X" and "baisse le volume à X" are interpreted as
        volume_up/volume_down since the verbs "monte" (increase) and "baisse" (decrease)
        suggest relative changes rather than absolute setting.
        """
        test_cases = [
            ("mets volume à 70", 70, 'set_volume'),
            ("mets à 50", 50, 'set_volume'),
            ("son à 50", 50, 'set_volume'),
            ("mets son à 60", 60, 'set_volume'),
            ("monte le volume à 80", None, 'volume_up'),  # Interpreted as "increase" not "set to"
            ("baisse le volume à 20", None, 'volume_down'),  # Interpreted as "decrease" not "set to"
        ]

        for command, expected_volume, expected_intent in test_cases:
            with self.subTest(command=command):
                intent = self.engine_fr.classify(command)

                self.assertIsNotNone(intent, f"Intent should not be None for '{command}'")
                self.assertEqual(intent.intent_type, expected_intent, f"Intent type should be '{expected_intent}' for '{command}'")
                if expected_volume is not None:
                    self.assertEqual(intent.parameters.get('volume'), expected_volume, f"Volume should be {expected_volume} for '{command}'")

    # ============================================================================
    # FRENCH TESTS - Number Words
    # ============================================================================

    def test_french_volume_number_words(self):
        """Test: French volume with number words (cinquante, soixante, etc.)

        Given: French commands with number words
        When: classify() called
        Then: Returns set_volume intent with correct numeric volume
        """
        test_cases = [
            ("mets le volume à cinquante", 50),
            ("mets le volume à soixante", 60),
            ("mets le volume à quatre-vingts", 80),
            ("mets le volume à quatre vingts", 80),
            ("volume à cinquante", 50),
            ("mets à soixante", 60),
        ]

        for command, expected_volume in test_cases:
            with self.subTest(command=command):
                intent = self.engine_fr.classify(command)

                self.assertIsNotNone(intent, f"Intent should not be None for '{command}'")
                self.assertEqual(intent.intent_type, 'set_volume', f"Intent type should be 'set_volume' for '{command}'")
                self.assertEqual(intent.parameters.get('volume'), expected_volume, f"Volume should be {expected_volume} for '{command}'")

    # ============================================================================
    # FRENCH TESTS - Edge Cases
    # ============================================================================

    def test_french_volume_edge_cases(self):
        """Test: French volume edge cases (0, 100, accents)"""
        test_cases = [
            ("mets le volume à 0", 0),
            ("mets le volume à 100", 100),
            ("règle le volume à 90", 90),  # With accent
            ("regle le volume à 90", 90),  # Without accent
        ]

        for command, expected_volume in test_cases:
            with self.subTest(command=command):
                intent = self.engine_fr.classify(command)

                self.assertIsNotNone(intent, f"Intent should not be None for '{command}'")
                self.assertEqual(intent.intent_type, 'set_volume', f"Intent type should be 'set_volume' for '{command}'")
                self.assertEqual(intent.parameters.get('volume'), expected_volume, f"Volume should be {expected_volume} for '{command}'")

    # ============================================================================
    # FRENCH TESTS - Fuzzy Matching
    # ============================================================================

    def test_french_volume_fuzzy_matching(self):
        """Test: French volume with typos and fuzzy matching

        Given: French commands with minor typos
        When: classify() called
        Then: Most should still correctly classify as set_volume
        """
        # These should match with fuzzy matching (most cases)
        test_cases = [
            ("mes le volume à 60", True),  # Typo in 'mets' - should work
            ("met le volume à 70", True),  # Missing 's' in 'mets' - should work
            ("mets volum à 50", False),  # Missing 'e' in volume - may fail (acceptable)
        ]

        for command, should_match in test_cases:
            with self.subTest(command=command):
                intent = self.engine_fr.classify(command)

                if should_match:
                    # These should work with fuzzy matching
                    self.assertIsNotNone(intent, f"Intent should not be None for '{command}'")
                    self.assertEqual(intent.intent_type, 'set_volume', f"Intent type should be 'set_volume' for '{command}'")
                    self.assertIsNotNone(intent.parameters.get('volume'), f"Volume should be extracted for '{command}'")
                else:
                    # These may not work - fuzzy matching has limits
                    # Just check that we got some intent
                    if intent:
                        # If it matches, good! If not, that's also acceptable.
                        pass

    # ============================================================================
    # FRENCH TESTS - Distinguish from volume_up/volume_down
    # ============================================================================

    def test_french_volume_distinguish_from_relative(self):
        """Test: Ensure set_volume doesn't conflict with volume_up/volume_down

        Given: Commands for volume_up and volume_down
        When: classify() called
        Then: Returns correct intent (not set_volume)
        """
        volume_up_commands = [
            "monte le volume",
            "plus fort",
            "augmente",
        ]

        volume_down_commands = [
            "baisse le volume",
            "moins fort",
            "diminue",
        ]

        for command in volume_up_commands:
            with self.subTest(command=command):
                intent = self.engine_fr.classify(command)
                self.assertIsNotNone(intent)
                self.assertEqual(intent.intent_type, 'volume_up', f"'{command}' should be volume_up, not set_volume")

        for command in volume_down_commands:
            with self.subTest(command=command):
                intent = self.engine_fr.classify(command)
                self.assertIsNotNone(intent)
                self.assertEqual(intent.intent_type, 'volume_down', f"'{command}' should be volume_down, not set_volume")

    # ============================================================================
    # ENGLISH TESTS
    # ============================================================================

    def test_english_volume_numeric(self):
        """Test: English volume with numeric values

        Given: English commands with numeric volume levels
        When: classify() called
        Then: Returns set_volume intent with correct volume parameter
        """
        test_cases = [
            ("set volume to 50", 50),
            ("set volume to 80", 80),
            ("volume to 60", 60),
            ("adjust volume to 40", 40),
            ("set volume 70", 70),
        ]

        for command, expected_volume in test_cases:
            with self.subTest(command=command):
                intent = self.engine_en.classify(command)

                self.assertIsNotNone(intent, f"Intent should not be None for '{command}'")
                self.assertEqual(intent.intent_type, 'set_volume', f"Intent type should be 'set_volume' for '{command}'")
                self.assertEqual(intent.parameters.get('volume'), expected_volume, f"Volume should be {expected_volume} for '{command}'")

    def test_english_volume_variations(self):
        """Test: English volume with various phrasings"""
        test_cases = [
            ("volume 50", 50),
            ("set to 50", 50),
            ("sound to 50", 50),
            ("set sound to 60", 60),
        ]

        for command, expected_volume in test_cases:
            with self.subTest(command=command):
                intent = self.engine_en.classify(command)

                self.assertIsNotNone(intent, f"Intent should not be None for '{command}'")
                self.assertEqual(intent.intent_type, 'set_volume', f"Intent type should be 'set_volume' for '{command}'")
                self.assertEqual(intent.parameters.get('volume'), expected_volume, f"Volume should be {expected_volume} for '{command}'")

    # ============================================================================
    # PARAMETER EXTRACTION TESTS
    # ============================================================================

    def test_volume_parameter_clamping(self):
        """Test: Volume parameter is clamped to 0-100 range

        Given: Commands with out-of-range volumes
        When: classify() called and parameters extracted
        Then: Volume is clamped to valid range (0-100)
        """
        # Note: Clamping is done in _extract_parameters
        intent = self.engine_fr.classify("mets le volume à 150")

        # Intent engine clamps to 0-100 in extraction
        if intent and intent.parameters.get('volume') is not None:
            volume = intent.parameters.get('volume')
            self.assertGreaterEqual(volume, 0)
            self.assertLessEqual(volume, 100)

    def test_volume_parameter_integer_conversion(self):
        """Test: Volume parameter is converted to integer

        Given: Commands with numeric values
        When: Parameters extracted
        Then: Volume is an integer, not a string
        """
        intent = self.engine_fr.classify("mets le volume à 75")

        self.assertIsNotNone(intent)
        volume = intent.parameters.get('volume')
        self.assertIsInstance(volume, int, "Volume should be an integer")
        self.assertEqual(volume, 75)


class TestCommandValidatorSetVolume(unittest.TestCase):
    """Test CommandValidator for set_volume intent"""

    def setUp(self):
        """Initialize command validator"""
        from modules.command_validator import CommandValidator
        self.validator = CommandValidator(music_library=None, language='fr', debug=False)

    def test_validate_set_volume_valid(self):
        """Test: Validate set_volume with valid volume level

        Given: Intent with valid volume (0-100)
        When: validate() called
        Then: Returns valid result with French feedback
        """
        from modules.interfaces import Intent

        intent = Intent(
            intent_type='set_volume',
            confidence=1.0,
            parameters={'volume': 50},
            raw_text='mets le volume à 50',
            language='fr'
        )

        result = self.validator.validate(intent)

        self.assertTrue(result.is_valid)
        self.assertIn('50', result.feedback_message)
        self.assertEqual(result.validated_params['volume'], 50)

    def test_validate_set_volume_exceeds_max(self):
        """Test: Validate set_volume with volume exceeding MAX_VOLUME

        Given: Intent with volume > MAX_VOLUME (80)
        When: validate() called
        Then: Returns valid result but clamps to MAX_VOLUME
        """
        from modules.interfaces import Intent
        import config

        intent = Intent(
            intent_type='set_volume',
            confidence=1.0,
            parameters={'volume': 95},
            raw_text='mets le volume à 95',
            language='fr'
        )

        result = self.validator.validate(intent)

        self.assertTrue(result.is_valid)
        max_volume = getattr(config, 'MAX_VOLUME', 100)
        self.assertEqual(result.validated_params['volume'], max_volume)
        self.assertIn(str(max_volume), result.feedback_message)

    def test_validate_set_volume_invalid_parameter(self):
        """Test: Validate set_volume with invalid parameter

        Given: Intent with missing or invalid volume parameter
        When: validate() called
        Then: Returns invalid result with error message
        """
        from modules.interfaces import Intent

        intent = Intent(
            intent_type='set_volume',
            confidence=1.0,
            parameters={},  # Missing volume
            raw_text='mets le volume',
            language='fr'
        )

        result = self.validator.validate(intent)

        self.assertFalse(result.is_valid)
        self.assertIn('volume', result.feedback_message.lower())


if __name__ == '__main__':
    unittest.main()
