"""
French continue intent tests (kid-friendly phrases).
"""

from pathlib import Path

from modules.intent_engine import IntentEngine
from tests.utils.fixture_loader import load_fixture


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_continue_intent_fr():
    engine_fr = IntentEngine(fuzzy_threshold=50, language='fr', debug=False)
    fixtures = load_fixture(FIXTURES_DIR / "intent_continue_cases_fr.json")

    for case in fixtures["continue"]:
        intent = engine_fr.classify(case["text"])
        assert intent is not None
        assert intent.intent_type == "continue"
